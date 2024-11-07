import os
import csv
import requests

# Specifica il percorso della cartella contenente i file CSV
folder_path = 'Scuole private'
output_file = 'istituti_privati.txt'


def get_place_id(indirizzo, city):
    url = 'https://nominatim.openstreetmap.org/search'
    params = {
        'street': indirizzo,
        'city': city,
        'state': 'Marche',
        'country': 'Italia',
        'addressdetails': 1,
        'extratags': 1,
        'namedetails': 1,
        'hierarchy': 1,
        'group_hierarchy': 1,
        'format': 'json',
    }
    headers = {
        'User-Agent': 'MamateamCeleste/1.0 (mamateamceleste@gmail.com)'
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    print(indirizzo, city)
    print(data)

    if data:
        return data
    return None


# Apri il file di output in modalità scrittura
with open(output_file, 'w') as output:
    # Itera attraverso tutti i file nella cartella
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)

            # Apri e leggi il file CSV
            with open(file_path, newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)

                # Itera attraverso le righe del CSV
                for row in reader:
                    istituto = row[1].replace("\'", "\\\'")
                    indirizzo = row[3].replace('c.da', 'contrada').replace('V.Le', 'Viale')
                    citta = row[2]
                    CAP = row[4]
                    provincia = row[0]

                    print(istituto)
                    indirizzo_completo = f'{indirizzo}, {citta}, {CAP}, Italia'
                    data = get_place_id(indirizzo, citta)
                    id = 'null'
                    if data:
                        id = data[0]['osm_type'][0:1] + str(data[0]['osm_id'])
                        print(id)

                    # Scrivi i dati formattati nel file di output
                    output.write(
                        f'[\'istituto\' => \'{istituto}\', '
                        f'\'citta\' => \'{citta}\', '
                        f'\'indirizzo\' => \'{indirizzo_completo.replace("\'", "\\\'")}\', '
                        f'\'osm_id\' => \'{id}\', '
                        f'\'CAP\' => \'{CAP}\', '
                        f'\'provincia\' => \'{provincia}\', '
                        f'\'telefono\' => \'{row[5].strip().replace("/", "")}\', '
                        f'\'link\' => \'\', '
                        f'\'privato\' => 1, '
                        f'\'created_at\' => now()],\n'
                    )

print(f'I dati formattati sono stati scritti in {output_file}')
