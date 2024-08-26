import os
import csv

# Specifica il percorso della cartella contenente i file CSV
folder_path = 'Scuole private'
output_file = 'output.txt'

# Apri il file di output in modalità scrittura
with open(output_file, 'w') as output:
    # Itera attraverso tutti i file nella cartella
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)

            # Apri e leggi il file CSV
            with open(file_path, newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Salta l'intestazione, se presente

                # Itera attraverso le righe del CSV
                for row in reader:
                    # Scrivi la riga formattata nel file di output
                    output.write(
                        f'[\'istituto\' => \'{row[1].replace('\'','\\\'')}\', '
                        f'\'citta\' => \'{row[2]}\', '
                        f'\'indirizzo\' => \'{row[3]}\', '
                        f'\'CAP\' => \'{row[4]}\', '
                        f'\'provincia\' => \'{row[0]}\', '
                        f'\'telefono\' => \'{row[5]}\', '
                        f'\'link\' => \'\', '
                        f'\'privato\' => 1, '
                        f'\'created_at\' => now()],\n'
                    )

print(f'I dati formattati sono stati scritti in {output_file}')
