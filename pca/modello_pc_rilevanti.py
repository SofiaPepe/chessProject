import pandas as pd
import os
import pingouin as pg

# --- CONFIG ---
dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/database_compositi.xlsx')
planning_pc_path = os.path.join(dir_base, '../pca/pca_planning_rilevanti.xlsx')
wm_pc_path = os.path.join(dir_base, '../pca/pca_wm_rilevanti.xlsx')
wmplanning_pc_path = os.path.join(dir_base, '../pca/pca_wmplanning_rilevanti.xlsx')

# 1. CARICA DATI

df = pd.read_excel(db_path)
planning_pc = pd.read_excel(planning_pc_path, index_col=0)
wm_pc = pd.read_excel(wm_pc_path, index_col=0)
wmplanning_pc = pd.read_excel(wmplanning_pc_path, index_col=0)


# Unisci le PC rilevanti al database (merge su index)
df = df.merge(planning_pc, left_index=True, right_index=True, how='left')
df = df.merge(wm_pc, left_index=True, right_index=True, how='left')
df = df.merge(wmplanning_pc, left_index=True, right_index=True, how='left')
# Forza tutte le colonne PC a numerico
for c in df.columns:
    if c.startswith('PC'):
        df[c] = pd.to_numeric(df[c], errors='coerce')

# 2. MODELLI LINEARI (come lmm_all)
results = []

for pc in [c for c in df.columns if c.startswith('PC')]:
    # Salta colonne completamente vuote o non numeriche
    if df[pc].dropna().empty:
        print(f"Salto {pc}: colonna vuota o non numerica")
        continue
    try:
        predictors = [c for c in ['gruppo', 'età', 'sesso'] if c in df.columns]
        temp_df = df[[pc] + predictors].copy()
        # Forza numerico e rimuovi inf/NaN
        temp_df[pc] = pd.to_numeric(temp_df[pc], errors='coerce')
        temp_df = temp_df.replace([float('inf'), float('-inf')], pd.NA).dropna()
        if temp_df.empty:
            print(f"Salto {pc}: nessun dato valido dopo la pulizia")
            continue
        lm = pg.linear_regression(temp_df[predictors], temp_df[pc])
        lm.insert(0, 'PC', pc)
        results.append(lm)
    except Exception as e:
        print(f"Errore su {pc}: {e}")

if results:
    out_path = os.path.join(dir_base, 'modello_pc_rilevanti.xlsx')
    pd.concat(results, ignore_index=True).to_excel(out_path, index=False)
    print(f"Risultati modello lineare salvati in {out_path}")
else:
    print("Nessun risultato disponibile.")
