
# Script per convertire file Excel o CSV in formato long
import pandas as pd

import pandas as pd
import re

# Carica il file Excel
file_path = r'C:\\Users\\spepe\\Desktop\\progetto_scacchi\\descrittive\\analisi_scacchi_definitive.xlsx'
df = pd.read_excel(file_path)

# Trova le colonne con _pre e _post
pre_cols = [col for col in df.columns if col.endswith('_PRE') or col.endswith('_pre')]
post_cols = [col for col in df.columns if col.endswith('_POST') or col.endswith('_post')]

# Trova le variabili base (senza suffisso)
base_cols = [col for col in df.columns if not re.search(r'(_PRE|_pre|_POST|_post)$', col)]

# Crea una lista di variabili comuni tra pre e post (ordine come nel file)
pre_base = [re.sub(r'(_PRE|_pre)$', '', col) for col in pre_cols]
post_base = [re.sub(r'(_POST|_post)$', '', col) for col in post_cols]
common_vars = []
for var in pre_base:
    if var in post_base:
        common_vars.append(var)

# Costruisci il dataframe long
long_rows = []
long_rows = []
for idx, row in df.iterrows():
    # Tempo 1 (pre)
    pre_data = {col: row[col] for col in base_cols}
    pre_data['tempo'] = 1
    for var in common_vars:
        pre_col = [c for c in pre_cols if re.sub(r'(_PRE|_pre)$', '', c) == var][0]
        pre_data[var] = row[pre_col]
    long_rows.append(pre_data)

    # Tempo 2 (post)
    post_data = {col: row[col] for col in base_cols}
    post_data['tempo'] = 2
    for var in common_vars:
        post_col = [c for c in post_cols if re.sub(r'(_POST|_post)$', '', c) == var][0]
        post_data[var] = row[post_col]
    long_rows.append(post_data)

# Ordine colonne: base_cols + ['tempo'] + common_vars
col_order = base_cols + ['tempo'] + common_vars
long_df = pd.DataFrame(long_rows)[col_order]

# Salva il file Excel
long_df.to_excel(r'C:\\Users\\spepe\\Desktop\\progetto_scacchi\\descrittive\\analisi_scacchi_definitive_long.xlsx', index=False)
print('File long creato!')
    long_rows.append(post_data)

# Crea il dataframe long
long_df = pd.DataFrame(long_rows)

# Salva sia in CSV che in Excel
out_csv = os.path.join(os.path.dirname(file_path), 'analisi_scacchi_definitive_long.csv')
out_xlsx = os.path.join(os.path.dirname(file_path), 'analisi_scacchi_definitive_long.xlsx')
long_df.to_csv(out_csv, index=False)
long_df.to_excel(out_xlsx, index=False)
print('File long creato sia in CSV che in Excel!')
