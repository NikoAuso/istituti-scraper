import bs4
import requests

urls = [
    ['http://www.marche.istruzione.it/AN_statali_S2.shtml', 'AN'],
    ['http://www.marche.istruzione.it/AP_statali_S2.shtml', 'AP'],
    ['http://www.marche.istruzione.it/MC_statali_S2.shtml', 'MC'],
    ['http://www.marche.istruzione.it/PS_statali_S2.shtml', 'PS']
]
output_file = 'istituti_pubblici.txt'

with open(output_file, 'w') as f:
    for tupla in urls:
        soup = bs4.BeautifulSoup(requests.get(tupla[0]).text, 'lxml')
        table = soup.find("table", {"class": "grigliascuole"})

        if table:
            rows = table.find_all("tr")[1:]  # Ignora l'intestazione

            for row in rows:

                columns = row.find_all("td")

                if len(columns) == 3:  # Controlla che ci siano 3 colonne
                    # Estraggo le informazioni necessarie
                    istituto = ' '.join(columns[0].find("strong").text.strip().split())
                    indirizzo_completo = [
                        element.replace('\t', '').replace('\r', '').strip()
                        for element in columns[0].text.strip().split("\n")
                        if element.strip()  # Filtra elementi vuoti o solo spazi
                    ]
                    indirizzo_completo = [element for element in indirizzo_completo if element][-2:]
                    #print(indirizzo_completo)

                    indirizzo = ' '.join(indirizzo_completo[0].strip().split())
                    provincia = tupla[1]
                    citta = ' '.join(indirizzo_completo[1].split()[1:])
                    cap = indirizzo_completo[1].split()[0]

                    telefono = columns[1].text.strip().split("\n")[0].split("-")[0].split("�")[0].split("–")[0]
                    da_rimuovere = ["tel. ", "segr.", "dir.", "(dri.)","()", "(centr.)", "fax"]
                    for sottostringa in da_rimuovere:
                        telefono = telefono.replace(sottostringa, "")
                    link = columns[1].text.strip().split("\n")[-1].strip()
                    if 'http' not in link and 'www' not in link:
                        link = ''

                    # Scrivi i dati formattati nel file di output
                    f.write(
                        f'[\'istituto\' => \'{istituto.replace('\'','\\\'')}\', '
                        f'\'citta\' => \'{citta.replace('\'','\\\'')}\', '
                        f'\'indirizzo\' => \'{indirizzo.replace('\'','\\\'')}\', '
                        f'\'CAP\' => \'{cap}\', '
                        f'\'provincia\' => \'{provincia.replace('\'','\\\'')}\', '
                        f'\'telefono\' => \'{telefono}\', '
                        f'\'link\' => \'{link}\', '
                        f'\'privato\' => 0, '
                        f'\'created_at\' => now()],\n'
                    )
print(f'I dati formattati sono stati scritti in {output_file}')
