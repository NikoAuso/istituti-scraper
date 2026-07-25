"""Check del normalizzatore/parser/filtri. Nessuna rete. Esegui: python test_extract.py"""

import extract

STATALE = {
    "ANNOSCOLASTICO": "202627", "AREAGEOGRAFICA": "CENTRO", "REGIONE": "MARCHE",
    "PROVINCIA": "ANCONA", "CODICESCUOLA": "ANPC010005",
    "DENOMINAZIONESCUOLA": 'LICEO CLASSICO "RINALDINI"',
    "INDIRIZZOSCUOLA": "VIA CANALE 1", "CAPSCUOLA": "60125",
    "CODICECOMUNESCUOLA": "A271", "DESCRIZIONECOMUNE": "ANCONA",
    "DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA": "LICEO CLASSICO",
    "INDIRIZZOEMAILSCUOLA": "info@rinaldini.edu.it",
    "INDIRIZZOPECSCUOLA": "Non Disponibile", "SITOWEBSCUOLA": "  ",
}
PARITARIA = {  # schema ridotto: mancano codice/istituto di riferimento e caratteristica
    "ANNOSCOLASTICO": "202627", "REGIONE": "LIGURIA", "PROVINCIA": "GENOVA",
    "CODICESCUOLA": "GE1E02300P", "DENOMINAZIONESCUOLA": "IST. DON BOSCO",
    "INDIRIZZOSCUOLA": "VIA CRISTOFOLI 8", "CAPSCUOLA": "16151",
    "DESCRIZIONECOMUNE": "GENOVA",
    "DESCRIZIONETIPOLOGIAGRADOISTRUZIONESCUOLA": "SCUOLA PRIMARIA NON STATALE",
}


def test_clean():
    assert extract.clean("Non Disponibile") is None
    assert extract.clean("  ") is None
    assert extract.clean(None) is None
    assert extract.clean("  VIA CANALE 1 ") == "VIA CANALE 1"


def test_normalize_statale():
    r = extract.normalize(STATALE, paritaria=False)
    assert r["codice"] == "ANPC010005"
    assert r["denominazione"] == 'LICEO CLASSICO "RINALDINI"'
    assert r["pec"] is None            # "Non Disponibile" -> null
    assert r["sito_web"] is None       # solo spazi -> null
    assert r["paritaria"] is False


def test_normalize_paritaria_schema_ridotto():
    r = extract.normalize(PARITARIA, paritaria=True)
    assert r["paritaria"] is True
    assert r["comune"] == "GENOVA"
    assert r["codice_istituto_riferimento"] is None  # colonna assente -> null
    assert r["caratteristica"] is None


def test_livello():
    # etichette per tipo istituto -> tutte secondaria di II grado
    assert extract.livello("LICEO SCIENTIFICO") == "secondaria-ii"
    assert extract.livello("ISTITUTO SUPERIORE") == "secondaria-ii"
    assert extract.livello("IST PROF PER I SERVIZI COMMERCIALI") == "secondaria-ii"
    assert extract.livello("IST TEC COMMERCIALE E PER GEOMETRI") == "secondaria-ii"
    assert extract.livello("ISTITUTO D'ARTE") == "secondaria-ii"
    assert extract.livello("SCUOLA SEC. SECONDO GRADO NON STATALE") == "secondaria-ii"
    # livelli reali
    assert extract.livello("SCUOLA INFANZIA NON STATALE") == "infanzia"
    assert extract.livello("SCUOLA PRIMARIA") == "primaria"
    assert extract.livello("SCUOLA PRIMO GRADO") == "secondaria-i"
    assert extract.livello("ISTITUTO COMPRENSIVO") == "comprensivo"
    assert extract.livello("CENTRO TERRITORIALE") == "altro"
    assert extract.livello(None) is None


def test_matches():
    r = extract.normalize(STATALE, paritaria=False)
    assert extract.matches(r, "MARCHE", None, None)
    assert extract.matches(r, "marche", "ancona", "LICEO")  # grado grezzo, case-insensitive
    assert extract.matches(r, None, None, None, liv="secondaria-ii")
    assert not extract.matches(r, None, None, None, liv="infanzia")
    assert not extract.matches(r, "LAZIO", None, None)


def test_loose_match():
    # grafie MIUR abbreviate vs nomi estesi della UI
    assert extract._loose("FRIULI-VENEZIA G.", "FRIULI VENEZIA GIULIA")
    assert extract._loose("PESARO E URBINO", "PESARO")       # provincia parziale
    assert extract._loose("EMILIA ROMAGNA", "emilia romagna")
    assert not extract._loose("MARCHE", "LAZIO")


def test_parse_csv():
    text = (
        "CODICESCUOLA,DENOMINAZIONESCUOLA,REGIONE\n"
        'ANPC010005,"LICEO ""RINALDINI""",MARCHE\n'
    )
    rows = extract.parse_csv(text, paritaria=False)
    assert len(rows) == 1
    assert rows[0]["denominazione"] == 'LICEO "RINALDINI"'  # virgolette CSV gestite
    assert rows[0]["regione"] == "MARCHE"


def test_latest_filename():
    html = "...SCUANAGRAFESTAT20242520250831.csv... SCUANAGRAFESTAT20262720260901.csv..."
    assert extract.latest_filename(html, "SCUANAGRAFESTAT") == "SCUANAGRAFESTAT20262720260901.csv"
    assert extract.latest_filename("niente", "SCUANAGRAFESTAT") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("Tutti i test passati.")
