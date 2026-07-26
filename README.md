# istituti-scraper

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

Estrae l'anagrafe di **tutte le scuole italiane** dai dati aperti ufficiali del Ministero
(Portale Unico dei Dati della Scuola, [dati.istruzione.it](https://dati.istruzione.it)) e
produce un **JSON pulito**. CLI + interfaccia web, solo Python standard library.

## Caratteristiche

- **Fonte ufficiale, diretta** — scarica i CSV del Ministero, nessuno scraping di pagine HTML: copertura nazionale, dato autorevole e stabile.
- **Statali + paritarie**, con filtri per regione, provincia, livello e grado.
- **Campo `livello` derivato** — riconduce le ~45 etichette grezze MIUR a un livello sintetico, così le superiori sono individuabili nonostante nel dato grezzo siano elencate per tipo (`LICEO SCIENTIFICO`, `IST PROF…`).
- **Nomi normalizzati** — campo `denominazione_estesa` con sigle espanse (`I.C.`→Istituto Comprensivo, `L.`→Liceo…), leggibile e più adatto alle mappe.
- **Geocoding a cascata** — quando la scuola è un POI OpenStreetMap dà coordinate dell'edificio + `osm_id`, con fallback a strada/comune; ogni punto è etichettato con `geo_precision`.
- **Interfaccia web** per generare, modificare a mano e salvare il JSON.
- **Zero dipendenze** — solo Python 3.8+ standard library.

## Uso da riga di comando

```bash
python extract.py                                            # tutta Italia, statali + paritarie
python extract.py --regione MARCHE --livello secondaria-ii   # superiori delle Marche
python extract.py --provincia ANCONA --paritarie             # solo paritarie di Ancona
python extract.py --regione MARCHE --geocode                 # aggiunge lat/lon (Nominatim)
```

Scrive `istituti.json` (opzione `-o` per cambiare percorso).

Opzioni: `--statali` / `--paritarie` (senza nessuna delle due = entrambe),
`--regione`, `--provincia` (nome esteso, es. `ANCONA`), `--livello`,
`--grado` (match parziale sull'etichetta grezza), `--geocode`, `--cache`, `-o/--output`.

`--livello` accetta: `infanzia`, `primaria`, `secondaria-i`, `secondaria-ii`, `comprensivo`, `altro`.

## Interfaccia web

```bash
python serve.py     # apri http://127.0.0.1:8000
```

Imposta le opzioni a video, premi **Genera**, modifica i dati direttamente in tabella,
premi **Salva nel JSON** per riscrivere `istituti.json`. Il server ascolta solo in locale.

## Schema del JSON

Ogni scuola è un oggetto con questi campi (valori mancanti = `null`):

| campo | note |
|-------|------|
| `codice` | codice meccanografico |
| `denominazione` | grafia grezza MIUR (sigle, virgolette) |
| `denominazione_estesa` | denominazione **normalizzata**: sigle espanse (con e senza punti), numeri romani preservati, virgolette rimosse, title-case |
| `indirizzo`, `cap`, `comune`, `codice_comune` | |
| `provincia`, `regione`, `area` | |
| `grado` | etichetta grezza MIUR (es. `LICEO SCIENTIFICO`) |
| `livello` | derivato: `infanzia`/`primaria`/`secondaria-i`/`secondaria-ii`/`comprensivo`/`altro` |
| `caratteristica` | (solo statali) |
| `codice_istituto_riferimento`, `istituto_riferimento` | (solo statali) |
| `email`, `pec`, `sito_web` | |
| `anno_scolastico` | |
| `paritaria` | `true` / `false` |
| `lat`, `lon` | sempre presenti; valorizzati con `--geocode`, altrimenti `null` (editabili a mano nell'interfaccia) |
| `osm_id` | riferimento OpenStreetMap della **scuola** (es. `w27784250`); solo quando il match è a livello scuola |
| `geo_precision` | qualità del punto: `school` (edificio+osm_id) / `street` (strada) / `comune` (centroide) / `null` |

Esempio di un elemento (alcuni campi omessi per brevità):

```json
{
  "codice": "APTD00201T",
  "denominazione": "ISTITUTO TECNICO ECONOMICO \"L. EINAUDI\"",
  "denominazione_estesa": "Istituto Tecnico Economico L. Einaudi",
  "indirizzo": "VIA LEGNANO 17",
  "cap": "63018",
  "comune": "PORTO SANT'ELPIDIO",
  "provincia": "FERMO",
  "regione": "MARCHE",
  "grado": "ISTITUTO TECNICO COMMERCIALE",
  "livello": "secondaria-ii",
  "email": "APIS00200G@istruzione.it",
  "sito_web": "www.polourbani.edu.it",
  "paritaria": false,
  "lat": 43.243, "lon": 13.763,
  "osm_id": "w27784250",
  "geo_precision": "school"
}
```

## Note sui dati

- La `provincia` usa il **nome esteso** (`ANCONA`, non `AN`); le regioni hanno grafie
  abbreviate (`FRIULI-VENEZIA G.`) — il filtro è tollerante alle varianti.
- **Valle d'Aosta** e **Trentino-Alto Adige / Bolzano** gestiscono anagrafi proprie e
  **non sono presenti** nel dataset nazionale.
- `denominazione_estesa` è una normalizzazione euristica (best-effort) di `denominazione`:
  utile per lettura e geocoding, ma la grafia grezza MIUR resta in `denominazione`.
- Il dato ufficiale non contiene coordinate: `--geocode` le ricava da
  [Nominatim](https://nominatim.org) con una **cascata a precisione decrescente**, così ogni
  scuola è geolocalizzata (`geo_precision` indica la qualità):
  1. **per nome** (nome normalizzato + comune), accettato solo se il risultato è un POI
     `amenity=school` → coordinate dell'edificio + `osm_id` della scuola;
  2. **per indirizzo** (strada) → `geo_precision=street`;
  3. **centroide del comune** (una sola richiesta per comune, condivisa) → `geo_precision=comune`.
  Rispetta la policy OSM (max 1 richiesta/secondo, fino a ~3 richieste/scuola) con cache su
  `geocache.json`. A scala nazionale conviene geocodare per regione/provincia e accumulare la cache.

## Test

```bash
python test_extract.py
```

## Licenza

Codice: **MIT**. Dati: [IODL 2.0](https://www.dati.gov.it/content/italian-open-data-license-v20) — © Ministero dell'Istruzione e del Merito.
