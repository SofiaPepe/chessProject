import pandas as pd
import os
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# --- CONFIG ---
dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/database_compositi.xlsx')

# 1. CARICA DATABASE

df = pd.read_excel(db_path)

# 2. DEFINISCI GRUPPI DI VARIABILI
planning_cols = [c for c in df.columns if 'planning' in c.lower() and not any(x in c.lower() for x in ['te','tp'])]
wm_cols = [c for c in df.columns if c.lower().startswith('wm') and not any(x in c.lower() for x in ['te','tp'])]
wmplanning_cols = [c for c in df.columns if (('wmplanning' in c.lower()) or ('wmp' in c.lower()) or ('pwm' in c.lower())) and not any(x in c.lower() for x in ['te','tp'])]

# Funzione PCA filtrata

def run_pca_relevant(cols, nome, file_name=None, var_threshold=0.8):
    if not cols:
        print(f'Nessuna colonna trovata per {nome}')
        return
    X = df[cols].dropna()
    if X.empty:
        print(f'Nessun dato valido per {nome}')
        return
    X_std = StandardScaler().fit_transform(X)
    pca = PCA()
    X_pca = pca.fit_transform(X_std)
    # Seleziona solo le PC che spiegano almeno var_threshold della varianza cumulata
    var_cum = pca.explained_variance_ratio_.cumsum()
    n_relevant = (var_cum < var_threshold).sum() + 1
    X_relevant = X_pca[:, :n_relevant]
    df_relevant = pd.DataFrame(X_relevant, columns=[f'PC{i+1}' for i in range(n_relevant)], index=X.index)
    if not file_name:
        file_name = f'pca_{nome}_rilevanti.xlsx'
    out_path = os.path.join(dir_base, file_name)
    df_relevant.to_excel(out_path, index=True)
    print(f'PC rilevanti per {nome} salvate in {out_path}')

# 3. ESEGUI PCA FILTRATA
run_pca_relevant(planning_cols, 'planning', file_name='pca_planning_rilevanti.xlsx')
run_pca_relevant(wm_cols, 'wm', file_name='pca_wm_rilevanti.xlsx')
run_pca_relevant(wmplanning_cols, 'wmplanning', file_name='pca_wmplanning_rilevanti.xlsx')
