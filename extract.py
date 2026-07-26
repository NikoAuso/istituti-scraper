#!/usr/bin/env python3
"""Estrattore dell'anagrafe delle scuole italiane dai dati aperti ufficiali MIUR.

Sorgente: Portale Unico dei Dati della Scuola (https://dati.istruzione.it) —
dataset "Anagrafe scuole statali" e "Anagrafe scuole paritarie", licenza IODL 2.0.
Nessuno scraping: si scaricano i CSV ufficiali e si normalizzano in un JSON pulito.
Solo libreria standard, nessuna dipendenza esterna.
"""

from __future__ import annotations

import argparse
import io
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://dati.istruzione.it/opendata/opendata/catalogo/elements1"
AREA_URL = f"{BASE}/?area=Scuole"
PAR_LEAF_URL = f"{BASE}/leaf/?datasetId=DS0410SCUANAGRAFEPAR"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "istituti-scraper/2.0 (+https://github.com/NikoAuso/istituti-scraper)"

# Il MIUR usa "Non Disponibile" (e stringa vuota) come valore nullo.
NULL_TOKENS = {"", "non disponibile", "-"}

# Colonna CSV MIUR -> campo del JSON normalizzato. Le paritarie hanno uno schema
# ridotto: le colonne assenti diventano semplicemente null (row.get()).
FIELD_MAP = {
    "CODICESCUOLA": "codice",
    "DENOMINAZIONESCUOLA": "denominazione",
    "INDIRIZZOSCUOLA": "indirizzo",
    "CAPSCUOLA": "cap",
    "CODICECOMUNESCUOLA": "codice_comune",
    "DESCRIZIONECOMUNE": "comune",
    "PROVINCIA": "provincia",
    "REGIONE": "regione",
    "AREAGEOGRAFICA": "area",
    "DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA": "grado",
    "DESCRIZIONECARATTERISTICASCUOLA": "caratteristica",
    "CODICEISTITUTORIFERIMENTO": "codice_istituto_riferimento",
    "DENOMINAZIONEISTITUTORIFERIMENTO": "istituto_riferimento",
    "INDIRIZZOEMAILSCUOLA": "email",
    "INDIRIZZOPECSCUOLA": "pec",
    "SITOWEBSCUOLA": "sito_web",
    "ANNOSCOLASTICO": "anno_scolastico",
}


# --- pure (testabili senza rete) ------------------------------------------

def clean(value: str | None) -> str | None:
    """Normalizza un campo: strip e conversione dei placeholder nulli MIUR."""
    if value is None:
        return None
    value = value.strip()
    return None if value.lower() in NULL_TOKENS else value


LIVELLI = ("infanzia", "primaria", "secondaria-i", "secondaria-ii", "comprensivo", "altro")


def livello(grado: str | None) -> str | None:
    """Riconduce le ~45 etichette grezze MIUR a un livello sintetico e filtrabile.
    Il campo grado mescola livelli reali (SCUOLA PRIMARIA) e tipi di istituto
    (LICEO SCIENTIFICO, IST PROF...), tutti riconducibili alla secondaria di II grado."""
    g = (grado or "").upper()
    if not g:
        return None
    if "INFANZIA" in g:
        return "infanzia"
    if "PRIMARIA" in g:
        return "primaria"
    if "PRIMO GRADO" in g:
        return "secondaria-i"
    if "SECONDO GRADO" in g:
        return "secondaria-ii"
    if "COMPRENSIVO" in g:
        return "comprensivo"
    if any(k in g for k in ("LICEO", "SUPERIORE", "TECNICO", "IST TEC", "PROF",
                            "MAGISTRALE", "D'ARTE")):
        return "secondaria-ii"
    return "altro"  # CENTRO TERRITORIALE (CPIA), CONVITTO, EDUCANDATO...


# Espansione delle sigle MIUR ricorrenti: rende il nome leggibile e più vicino
# alla grafia usata in OpenStreetMap (migliora il match del geocoding per nome).
NAME_ABBREV = {
    "I.C.": "Istituto Comprensivo", "IST.": "Istituto", "ISTIT.": "Istituto",
    "I.I.S.": "Istituto Istruzione Superiore",
    "I.I.S.S.": "Istituto Istruzione Secondaria Superiore",
    "I.S.I.S.": "Istituto Statale Istruzione Superiore",
    "I.S.I.S.S.": "Istituto Statale Istruzione Secondaria Superiore",
    "I.T.": "Istituto Tecnico", "I.T.C.": "Istituto Tecnico Commerciale",
    "I.T.C.G.": "Istituto Tecnico Commerciale e Geometri",
    "I.T.G.": "Istituto Tecnico Geometri", "I.T.I.": "Istituto Tecnico Industriale",
    "I.T.I.S.": "Istituto Tecnico Industriale", "I.T.E.": "Istituto Tecnico Economico",
    "I.T.T.": "Istituto Tecnico Tecnologico", "I.P.": "Istituto Professionale",
    "I.P.S.": "Istituto Professionale",
    "I.P.S.I.A.": "Istituto Professionale Industria e Artigianato",
    "I.P.S.E.O.A.": "Istituto Professionale Enogastronomia e Ospitalità",
    "I.P.S.S.": "Istituto Professionale Servizi Sociali",
    "L.S.": "Liceo Scientifico", "L.C.": "Liceo Classico", "L.A.": "Liceo Artistico",
    "L.S.U.": "Liceo Scienze Umane", "S.M.S.": "Scuola Media Statale", "S.M.": "Scuola Media",
    "D.D.": "Direzione Didattica", "C.D.": "Circolo Didattico",
    "C.P.I.A.": "Centro Provinciale Istruzione Adulti",
    "PROF.": "Professionale", "SEC.": "Secondaria", "NAZ.": "Nazionale", "STAT.": "Statale",
    "OMNICOMPR.": "Omnicomprensivo", "COMPR.": "Comprensivo", "CONV.": "Convitto",
}
# stesse sigle senza punti (IC, ITIS, ISIS...); si escludono le 2-lettere ambigue
# (LA articolo, LC/LS/SM/IT/IP troppo corte) per non espandere parole comuni.
_AMBIGUOUS_NODOT = {"LA", "LC", "LS", "LSU", "SM", "IT", "IP"}
NAME_ABBREV_NODOT = {k.replace(".", ""): v for k, v in NAME_ABBREV.items()
                     if k.replace(".", "") not in _AMBIGUOUS_NODOT}
# particelle che restano minuscole nel title-case italiano
_LOWER = {"di", "del", "della", "dei", "delle", "dello", "degli", "e", "da", "in", "a", "per"}


_ROMAN = re.compile(r"X{0,3}(IX|IV|V?I{0,3})")


def _is_roman(w: str) -> bool:
    u = w.upper()
    return bool(u) and set(u) <= {"I", "V", "X"} and _ROMAN.fullmatch(u) is not None


def _titlecase_it(s: str) -> str:
    out = []
    for i, w in enumerate(s.split(" ")):
        if not w:
            out.append(w)
        elif _is_roman(w):
            out.append(w.upper())                         # numeri romani: 'II', non 'Ii'
        elif i and w.lower() in _LOWER:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def clean_name(den: str | None) -> str | None:
    """Nome leggibile e normalizzato: toglie virgolette, espande le sigle, separa le
    iniziali attaccate ('M.PAGANO' -> 'M. Pagano'), title-case."""
    if not den:
        return None
    s = re.sub(r'["“”]', " ", den.strip())
    # "L." davanti al tipo di liceo = Liceo (le iniziali di nome proprio restano intatte)
    s = re.sub(r"\bL\.?\s*(?=(?:SCIENTIF|CLASSIC|ARTISTIC|LINGUISTIC|MUSICAL|COREUTIC|SCIENZE))",
               "Liceo ", s, flags=re.I)
    s = " ".join(NAME_ABBREV.get(t.upper(), NAME_ABBREV_NODOT.get(t.upper(), t))
                 for t in s.split())                                  # espandi sigle (con/senza punti)
    s = re.sub(r"\b([A-Za-z])\.(?=[A-Za-z])", r"\1. ", s)             # "M.PAGANO" -> "M. PAGANO"
    return _titlecase_it(re.sub(r"\s+", " ", s).strip())


def name_variants(record: dict) -> list[str]:
    """Query per il geocoding per nome: nome completo normalizzato + eventuale nome
    proprio tra virgolette (senza iniziali), es. ['Liceo Classico M. Pagano', 'Pagano']."""
    nome = record.get("denominazione_estesa")
    out = [nome] if nome else []
    m = re.search(r'["“]([^"”]+)["”]', record.get("denominazione") or "")
    if m:
        proper = re.sub(r"\b[A-Za-z]\.\s*", "", m.group(1))          # togli iniziali singole
        proper = _titlecase_it(re.sub(r"\s+", " ", proper).strip())
        if proper and proper.lower() != (nome or "").lower():
            out.append(proper)
    return out


def normalize(row: dict, paritaria: bool) -> dict:
    record = {field: clean(row.get(col)) for col, field in FIELD_MAP.items()}
    record["denominazione_estesa"] = clean_name(record["denominazione"])
    record["livello"] = livello(record["grado"])
    record["paritaria"] = paritaria
    record["lat"] = None  # geo sempre presenti; valorizzati da geocode()
    record["lon"] = None
    record["osm_id"] = None
    record["geo_precision"] = None  # school | street | comune | None
    return record


def _norm(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _loose(value: str | None, needle: str) -> bool:
    """Match tollerante alle grafie MIUR: 'FRIULI VENEZIA GIULIA' ~ 'FRIULI-VENEZIA G.',
    'PESARO' ~ 'PESARO E URBINO'. Confronto per sottostringa sui valori normalizzati."""
    a, b = _norm(value), _norm(needle)
    return len(b) >= 3 and (a.startswith(b) or b.startswith(a) or b in a)


def matches(record: dict, regione: str | None, provincia: str | None,
            grado: str | None, liv: str | None = None) -> bool:
    if regione and not _loose(record.get("regione"), regione):
        return False
    if provincia and not _loose(record.get("provincia"), provincia):
        return False
    if grado and grado.upper() not in (record.get("grado") or "").upper():
        return False
    if liv and record.get("livello") != liv:
        return False
    return True


def parse_csv(text: str, paritaria: bool) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return [normalize(row, paritaria) for row in reader]


def latest_filename(html: str, prefix: str) -> str | None:
    """Il nome file più recente per un prefisso. Il formato a larghezza fissa
    (annoscolastico + data generazione) rende l'ordine lessicale == cronologico."""
    names = re.findall(rf"{prefix}\d+\.csv", html)
    return max(names) if names else None


# --- rete -----------------------------------------------------------------

def _get(url: str, timeout: int = 90) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def resolve_urls(statali: bool, paritarie: bool) -> dict:
    urls = {}
    if statali:
        name = latest_filename(_get(AREA_URL), "SCUANAGRAFESTAT")
        if not name:
            raise RuntimeError("nessun file anagrafe statali trovato nel catalogo MIUR")
        urls["statali"] = f"{BASE}/{name}"
    if paritarie:
        name = latest_filename(_get(PAR_LEAF_URL), "SCUANAGRAFEPAR")
        if not name:
            raise RuntimeError("nessun file anagrafe paritarie trovato nel catalogo MIUR")
        urls["paritarie"] = f"{BASE}/{name}"
    return urls


def load(statali: bool = True, paritarie: bool = True, regione: str | None = None,
         provincia: str | None = None, grado: str | None = None,
         liv: str | None = None, log=print) -> list[dict]:
    urls = resolve_urls(statali, paritarie)
    records: list[dict] = []
    for kind, url in urls.items():
        log(f"Scarico anagrafe {kind}: {url.rsplit('/', 1)[-1]}")
        rows = parse_csv(_get(url), paritaria=(kind == "paritarie"))
        kept = [r for r in rows if matches(r, regione, provincia, grado, liv)]
        log(f"  {len(kept)}/{len(rows)} scuole dopo i filtri")
        records.extend(kept)
    return records


SCHOOL_TYPES = {"school", "kindergarten", "college", "university"}


def _query(params: dict) -> list:
    """Ricerca Nominatim grezza (top 5, solo Italia). Ritorna la lista dei risultati."""
    p = {**params, "format": "jsonv2", "limit": "5", "countrycodes": "it"}
    try:
        return json.loads(_get(f"{NOMINATIM_URL}?{urllib.parse.urlencode(p)}", timeout=30))
    except Exception:
        return []


def _osm_ref(r: dict) -> str | None:
    t, i = r.get("osm_type"), r.get("osm_id")
    return f"{t[0]}{i}" if t and i else None


def _school_poi(results: list) -> dict | None:
    for r in results:
        if (r.get("category") or r.get("class")) == "amenity" and r.get("type") in SCHOOL_TYPES:
            return r
    return None


def geocode(records: list[dict], cache_path: str = "geocache.json",
            pause: float = 1.0, log=print) -> list[dict]:
    """Geocoding a cascata via Nominatim, con livello di precisione per punto:
      1. per nome  -> POI scuola (amenity=school): coord edificio + osm_id della scuola
      2. indirizzo -> strada
      3. comune    -> centroide (cache condivisa: un comune si risolve una volta sola)
    Cache su disco keyed per query: le run successive saltano il già risolto.
    Rispetta la policy OSM (max 1 req/s)."""
    cache_file = Path(cache_path)
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}

    def cached(params: dict) -> list:
        key = json.dumps(params, sort_keys=True, ensure_ascii=False)
        if key not in cache:
            cache[key] = _query(params)
            cache_file.write_text(json.dumps(cache, ensure_ascii=False))
            time.sleep(pause)
        return cache[key]

    def place(record, r, precision, osm=None):
        record["lat"], record["lon"] = float(r["lat"]), float(r["lon"])
        record["osm_id"], record["geo_precision"] = osm, precision

    for i, record in enumerate(records, 1):
        record["lat"] = record["lon"] = record["osm_id"] = None
        record["geo_precision"] = None
        comune, indirizzo = record.get("comune"), record.get("indirizzo")

        placed = False
        for q in name_variants(record) if comune else []:          # 1. per nome
            poi = _school_poi(cached({"q": f"{q}, {comune}, Italia"}))
            if poi:
                place(record, poi, "school", _osm_ref(poi))
                placed = True
                break
        if not placed and indirizzo and comune:                    # 2. indirizzo
            res = cached({"street": indirizzo, "city": comune, "country": "Italia"})
            if res:
                place(record, res[0], "street")
                placed = True
        if not placed and comune:                                  # 3. centroide comune
            res = cached({"q": f"{comune}, Italia"})
            if res:
                place(record, res[0], "comune")

        if i % 50 == 0:
            log(f"  geocoding: {i}/{len(records)}")
    return records


def build(opts: dict, log=print) -> list[dict]:
    records = load(
        statali=opts.get("statali", True),
        paritarie=opts.get("paritarie", True),
        regione=opts.get("regione"),
        provincia=opts.get("provincia"),
        grado=opts.get("grado"),
        liv=opts.get("livello"),
        log=log,
    )
    if opts.get("geocode"):
        if len(records) > 500:
            log(f"ATTENZIONE: geocoding a cascata di {len(records)} scuole a 1 req/s "
                f"(fino a ~3 richieste/scuola). Conviene filtrare o geocodare per regione.")
        geocode(records, cache_path=opts.get("cache", "geocache.json"), log=log)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--statali", action="store_true", help="solo scuole statali")
    parser.add_argument("--paritarie", action="store_true", help="solo scuole paritarie")
    parser.add_argument("--regione", help="filtra per regione (es. MARCHE)")
    parser.add_argument("--provincia", help="filtra per provincia, nome esteso (es. ANCONA)")
    parser.add_argument("--livello", choices=LIVELLI, help="filtra per livello sintetico")
    parser.add_argument("--grado", help="filtra per etichetta grado grezza (match parziale)")
    parser.add_argument("--geocode", action="store_true", help="aggiungi lat/lon via Nominatim")
    parser.add_argument("--cache", default="geocache.json", help="file cache geocoding")
    parser.add_argument("-o", "--output", default="istituti.json", help="file JSON di output")
    args = parser.parse_args(argv)

    # nessun flag di sorgente => entrambe
    statali = args.statali or not (args.statali or args.paritarie)
    paritarie = args.paritarie or not (args.statali or args.paritarie)

    records = build({
        "statali": statali, "paritarie": paritarie,
        "regione": args.regione, "provincia": args.provincia,
        "grado": args.grado, "livello": args.livello,
        "geocode": args.geocode, "cache": args.cache,
    })
    Path(args.output).write_text(json.dumps(records, ensure_ascii=False, indent=1))
    print(f"Scritti {len(records)} istituti in {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
