import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

import os
import pandas as pd
from scipy.stats import pearsonr

dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/analisi_scacchi_definitive.xlsx')
out_path = os.path.join(dir_base, 'correlazioni_tutte.xlsx')
df = pd.read_excel(db_path)


# Converte tutte le colonne non numeriche in valori numerici (dove possibile)
df_encoded = df.copy()
for col in df.columns:
    if df[col].dtype == 'object':
        try:
            df_encoded[col] = pd.to_numeric(df[col], errors='coerce')
        except Exception:
            df_encoded[col] = df[col].astype('category').cat.codes

# Calcola tutte le correlazioni e p-value
results = []
cols = df_encoded.columns
for i in range(len(cols)):
    for j in range(i+1, len(cols)):
        x, y = cols[i], cols[j]
        try:
            r, p = pearsonr(df_encoded[x].dropna(), df_encoded[y].dropna())
            if pd.notnull(r) and pd.notnull(p):
                results.append({'Var1': x, 'Var2': y, 'r': r, 'p': p})
        except Exception:
            continue

# Salva tutte le correlazioni (significative e non)
if results:
    df_results = pd.DataFrame(results)
    df_results.to_excel(out_path, index=False)
    print(f"File salvato: {out_path}")
else:
    print("Nessuna correlazione calcolabile.")
