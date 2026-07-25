# istituti-scraper

Estrae l'anagrafe delle **scuole italiane** dai dati aperti ufficiali del Ministero
(Portale Unico dei Dati della Scuola, [dati.istruzione.it](https://dati.istruzione.it)) e
produce un JSON pulito. Scarica i CSV ufficiali direttamente dal sito del Ministero:
nessuno scraping di pagine HTML, copertura nazionale, fonte autorevole e stabile.

Solo Python 3 standard library, **nessuna dipendenza** da installare.

## Uso da riga di comando

```bash
python extract.py                                     # tutta Italia, statali + paritarie
python extract.py --regione MARCHE --livello secondaria-ii   # superiori delle Marche
python extract.py --provincia AN --paritarie          # solo paritarie di Ancona
python extract.py --regione MARCHE --geocode          # aggiunge lat/lon (Nominatim)
```

Scrive `istituti.json` (opzione `-o` per cambiare percorso).

Opzioni: `--statali` / `--paritarie` (senza nessuna delle due = entrambe),
`--regione`, `--provincia` (nome esteso, es. `ANCONA`), `--livello`, `--grado` (match parziale sull'etichetta
grezza), `--geocode`, `--cache`, `-o/--output`.

`--livello` è un campo sintetico derivato dalle ~45 etichette MIUR:
`infanzia`, `primaria`, `secondaria-i`, `secondaria-ii`, `comprensivo`, `altro`
(nel dato grezzo le superiori sono elencate per tipo: `LICEO SCIENTIFICO`, `IST PROF…`, ecc.).

## Interfaccia web

```bash
python serve.py     # apri http://127.0.0.1:8000
```

Imposta le opzioni a video, premi **Genera**, modifica i dati direttamente in tabella,
premi **Salva nel JSON** per riscrivere `istituti.json`.

## Schema del JSON

Ogni scuola è un oggetto con questi campi (valori mancanti = `null`):

| campo | note |
|-------|------|
| `codice` | codice meccanografico |
| `denominazione` | |
| `indirizzo`, `cap`, `comune`, `codice_comune` | |
| `provincia`, `regione`, `area` | |
| `grado` | etichetta grezza MIUR (es. `LICEO SCIENTIFICO`) |
| `livello` | derivato: `infanzia`/`primaria`/`secondaria-i`/`secondaria-ii`/`comprensivo`/`altro` |
| `caratteristica` | (solo statali) |
| `codice_istituto_riferimento`, `istituto_riferimento` | (solo statali) |
| `email`, `pec`, `sito_web` | |
| `anno_scolastico` | |
| `paritaria` | `true` / `false` |
| `lat`, `lon` | solo con `--geocode` |

## Geocoding

Il dato ufficiale non contiene coordinate. Con `--geocode` vengono richieste a
[Nominatim](https://nominatim.org) rispettando la policy OSM (max 1 richiesta/secondo)
con cache su `geocache.json` (le run successive saltano gli indirizzi già risolti).
A scala nazionale sono ~55.000 scuole: conviene geocodare solo un sottoinsieme filtrato.

## Test

```bash
python test_extract.py
```

## Licenza

Codice: MIT. Dati: [IODL 2.0](https://www.dati.gov.it/content/italian-open-data-license-v20) — © Ministero dell'Istruzione e del Merito.
