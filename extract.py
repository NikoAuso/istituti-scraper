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


def normalize(row: dict, paritaria: bool) -> dict:
    record = {field: clean(row.get(col)) for col, field in FIELD_MAP.items()}
    record["livello"] = livello(record["grado"])
    record["paritaria"] = paritaria
    record["lat"] = None  # sempre presenti; valorizzati da geocode()
    record["lon"] = None
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


def _nominatim(indirizzo: str, comune: str) -> dict | None:
    params = urllib.parse.urlencode({
        "street": indirizzo, "city": comune, "country": "Italia",
        "format": "json", "limit": 1,
    })
    try:
        data = json.loads(_get(f"{NOMINATIM_URL}?{params}", timeout=30))
    except Exception:
        return None
    if not data:
        return None
    return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}


def geocode(records: list[dict], cache_path: str = "geocache.json",
            pause: float = 1.0, log=print) -> list[dict]:
    """Arricchisce con lat/lon via Nominatim. Rispetta la policy OSM (max 1 req/s)
    e mantiene una cache su disco: le run successive saltano gli indirizzi già risolti."""
    cache_file = Path(cache_path)
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    misses = 0
    for i, record in enumerate(records, 1):
        indirizzo, comune = record.get("indirizzo"), record.get("comune")
        if not indirizzo or not comune:
            record["lat"] = record["lon"] = None
            continue
        key = f"{indirizzo}|{comune}|{record.get('cap') or ''}".lower()
        if key not in cache:
            cache[key] = _nominatim(indirizzo, comune)
            cache_file.write_text(json.dumps(cache, ensure_ascii=False))
            misses += 1
            if misses % 50 == 0:
                log(f"  geocoding: {i}/{len(records)}")
            time.sleep(pause)
        hit = cache[key]
        record["lat"] = hit["lat"] if hit else None
        record["lon"] = hit["lon"] if hit else None
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
        if len(records) > 2000:
            log(f"ATTENZIONE: geocoding di {len(records)} scuole a 1 req/s "
                f"(~{len(records) // 60} min). Conviene filtrare prima.")
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
