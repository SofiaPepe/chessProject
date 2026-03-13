import pandas as pd
import re

# Carica il file Excel
file_path = 'database.xlsx'
df = pd.read_excel(file_path)

# Funzione per rimuovere spazi tra underscore e suffisso _PRE/_POST
pattern = re.compile(r'_\s+((PRE|POST))$')
def correggi_nome(col):
    # Rimuove spazi tra underscore e suffisso
    col = re.sub(pattern, r'_\1', col)  # carattere di controllo temporaneo
    col = col.replace('_', '_')
    return col.strip()

# Applica la correzione a tutte le colonne
nuovi_nomi = [correggi_nome(c) for c in df.columns]
df.columns = nuovi_nomi

# Salva il file corretto (sovrascrive quello vecchio)
df.to_excel('database.xlsx', index=False)
print('Colonne rinominate e spazi rimossi. File aggiornato.')
