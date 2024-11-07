from itertools import count

import bs4
import requests

urls = [
    ['http://www.marche.istruzione.it/AN_statali_S2.shtml', 'AN'],
    ['http://www.marche.istruzione.it/AP_statali_S2.shtml', 'AP'],
    ['http://www.marche.istruzione.it/MC_statali_S2.shtml', 'MC'],
    ['http://www.marche.istruzione.it/PS_statali_S2.shtml', 'PS']
]
output_file = 'istituti_pubblici.txt'


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


with (open(output_file, 'w') as f):
    i = 0
    for tupla in urls:
        soup = bs4.BeautifulSoup(requests.get(tupla[0]).text, 'lxml')
        table = soup.find("table", {"class": "grigliascuole"})

        if table:
            rows = table.find_all("tr")[1:]

            for row in rows:
                columns = row.find_all("td")

                if len(columns) == 3:
                    istituto = ' '.join(columns[0].find("strong").text.strip().split())
                    indirizzo_completo = [
                        element.replace('\t', '').replace('\r', '').strip()
                        for element in columns[0].text.strip().split("\n")
                        if element.strip()
                    ]
                    indirizzo_completo = [element for element in indirizzo_completo if element][-2:]

                    chart = [
                        'A.', 'B.', 'C.', 'D.', 'E.', 'F.', 'G.', 'H.', 'I.', 'J.', 'K.', 'L.',
                        'M.', 'N.', 'O.', 'P.', 'Q.', 'R.', 'S.', 'T.', 'U.', 'V.', 'W.', 'X.',
                        'Y.', 'Z.', 'snc', ', 60 - contrada Brancadoro', 'Mons.', '(Galleria Luzio)'
                    ]

                    indirizzo = ' '.join(indirizzo_completo[0].strip().split())

                    # Rimuovi eventuali parti indesiderate dall'indirizzo
                    for lettera in chart:
                        indirizzo = indirizzo.replace(lettera, '')
                    indirizzo = indirizzo.replace('  ', ' ')  # Rimuovi eventuali spazi doppi

                    provincia = tupla[1]
                    citta = ' '.join(indirizzo_completo[1].split()[1:])
                    CAP = indirizzo_completo[1].split()[0]

                    telefono = columns[1].text.strip().split("\n")[0].split("-")[0].split("�")[0].split("–")[0]
                    da_rimuovere = ["tel. ", "segr.", "dir.", "(dri.)", "()", "(centr.)", "fax"]
                    for sottostringa in da_rimuovere:
                        telefono = telefono.replace(sottostringa, "")
                    link = columns[1].text.strip().split("\n")[-1].strip()
                    if 'http' not in link and 'www' not in link:
                        link = ''

                    # if indirizzo_completo == 'via Montani, FERMO, 63900 Italia':
                    #     place_id = 66993332
                    # elif indirizzo_completo == 'via dello Sport, SAN BENEDETTO DEL TRONTO, 63074, Italia':
                    #     place_id = 99972976
                    # elif indirizzo_completo == 'Località San Paolo, , CAMERINO, 62032, Italia':
                    #     place_id = 371830308
                    # elif indirizzo_completo == ' Di Pietro, 12, MACERATA, 62100, Italia':
                    #     place_id = 67228805
                    # elif indirizzo_completo == 'via lli Cioci, 2, MACERATA, 62100, Italia':
                    #     place_id = 66476397
                    # elif indirizzo_completo == 'via lli Cioci, 6, MACERATA, 62100, Italia':
                    #     place_id = 99488040
                    # elif indirizzo_completo == 'via Matteotti, 18, SAN GINESIO, 62026, Italia':
                    #     place_id = 67103280
                    # elif indirizzo_completo == 'corso Cavour, , MACERATA, 62100, Italia':
                    #     place_id = 67310932
                    # elif indirizzo_completo == 'via Gasparrini, 11, MACERATA, 62100, Italia':
                    #     place_id = 100096869
                    # elif indirizzo_completo == 'viale Don Bosco, 16, FOSSOMBRONE, 61034, Italia':
                    #     place_id = 66670826
                    # elif indirizzo_completo == 'via Kennedy, 30, FANO, 61032, Italia':
                    #     place_id = 67078326
                    # elif indirizzo_completo == 'ITE Cagli, IPSIA Cagli, IPSAR Piobbicovia Giovanni Santi, 23, CAGLI, 61043, Italia':
                    #     place_id = 100430290
                    # else:
                    print(istituto)
                    indirizzo_completo = f'{indirizzo}, {citta}, {CAP}, Italia'
                    data = get_place_id(indirizzo, citta)
                    id = 'null'
                    if data:
                        id = data[0]['osm_type'][0:1] + str(data[0]['osm_id'])
                        print(id)

                    # Scrivi i dati formattati nel file di output
                    f.write(
                        f'[\'istituto\' => \'{istituto.replace("\'", "\\\'")}\', '
                        f'\'citta\' => \'{citta.replace("\'", "\\\'")}\', '
                        f'\'indirizzo\' => \'{indirizzo_completo.replace("\'", "\\\'")}\', '
                        f'\'osm_id\' => \'{id}\', '
                        f'\'CAP\' => \'{CAP}\', '
                        f'\'provincia\' => \'{provincia.replace("\'", "\\\'")}\', '
                        f'\'telefono\' => \'{telefono}\', '
                        f'\'link\' => \'{link}\', '
                        f'\'privato\' => 0, '
                        f'\'created_at\' => now()],\n'
                    )

print(f'I dati formattati sono stati scritti in {output_file}')
