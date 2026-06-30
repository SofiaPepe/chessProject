import pandas as pd
import os
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from pathlib import Path
import sys

# --- CONFIG ---
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "output" / "pca"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
dir_base = str(OUTPUT_DIR)
sys.path.append(str(ROOT / "analysis" / "descriptives"))
from add_composites import build_composite_dataframe  # noqa: E402

# 1. LOAD DATABASE

df = build_composite_dataframe()

# 2. DEFINE VARIABLE GROUPS
planning_cols = [c for c in df.columns if 'planning' in c.lower() and not any(x in c.lower() for x in ['te','tp'])]
wm_cols = [c for c in df.columns if c.lower().startswith('wm') and not any(x in c.lower() for x in ['te','tp'])]
wmplanning_cols = [c for c in df.columns if (('wmplanning' in c.lower()) or ('wmp' in c.lower()) or ('pwm' in c.lower())) and not any(x in c.lower() for x in ['te','tp'])]

# Funzione PCA filtrata

def run_pca_relevant(cols, name, file_name=None, var_threshold=0.8):
    if not cols:
        print(f'No column found for {name}')
        return
    X = df[cols].dropna()
    if X.empty:
        print(f'No valid data for {name}')
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
        file_name = f'relevant_pcs_{name}.xlsx'
    out_path = os.path.join(dir_base, file_name)
    df_relevant.to_excel(out_path, index=True)
    print(f'Relevant PCs for {name} saved to {out_path}')

# 3. ESEGUI PCA FILTRATA
run_pca_relevant(planning_cols, 'planning', file_name='relevant_pcs_planning.xlsx')
run_pca_relevant(wm_cols, 'wm', file_name='relevant_pcs_wm.xlsx')
run_pca_relevant(wmplanning_cols, 'wmplanning', file_name='relevant_pcs_wmplanning.xlsx')
