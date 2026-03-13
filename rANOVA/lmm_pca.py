import pandas as pd
import pingouin as pg
import os

# --- CONFIG ---
dir_base = os.path.dirname(os.path.abspath(__file__))
scores_path = os.path.join(dir_base, '../pca/scores_pca_unificato.xlsx')
df = pd.read_excel(scores_path, index_col=0)

# Identifica tutte le PC (colonne che terminano con _pre e _post)
pc_pre = [c for c in df.columns if c.endswith('_pre')]
pc_post = [c for c in df.columns if c.endswith('_post')]

# Trova la base name delle PC (es: PC1_planning)
pc_basenames = set([c.replace('_pre','').replace('_post','') for c in pc_pre])

# Variabili di gruppo, età, sesso (adatta se necessario)
group_col = 'gruppo'
eta_col = 'età'
sesso_col = 'sesso'
id_col = df.index.name if df.index.name else 'ID'

# Risultati
lmm_results = []

for base in pc_basenames:
    pre_col = base + '_pre'
    post_col = base + '_post'
    if pre_col not in df.columns or post_col not in df.columns:
        continue
    # Usa solo le colonne delle PC e le info minime già presenti nel file PC
    temp = df[[pre_col, post_col, group_col, eta_col, sesso_col]].copy()
    # Wide to long
    long_df = pd.melt(temp.reset_index(), id_vars=[id_col, group_col, eta_col, sesso_col],
                      value_vars=[pre_col, post_col], var_name='tempo', value_name='valore')
    long_df['tempo_num'] = long_df['tempo'].str.endswith('post').astype(int)
    long_df['interazione'] = long_df[group_col] * long_df['tempo_num']
    # Conversione esplicita a numerico
    for col in [group_col, 'tempo_num', 'interazione', eta_col, sesso_col, 'valore']:
        long_df[col] = pd.to_numeric(long_df[col], errors='coerce')
    # Rimuovi righe con NaN o Inf nei predittori o nella variabile dipendente
    predictors = [group_col, 'tempo_num', 'interazione', eta_col, sesso_col]
    long_df = long_df.dropna(subset=predictors + ['valore'])
    if long_df.empty or long_df[group_col].nunique() < 2:
        continue
    try:
        lm = pg.linear_regression(long_df[predictors], long_df['valore'])
        lm.insert(0, 'PC', base)
        lmm_results.append(lm)
    except Exception as e:
        print(f'Errore su {base}: {e}')

# Salva risultati
out_path = os.path.join(dir_base, 'lmm_pca_risultati.xlsx')
if lmm_results:
    pd.concat(lmm_results).to_excel(out_path, index=False)
    print(f'Risultati LMM PCA salvati in: {out_path}')
else:
    print('Nessun risultato LMM calcolato.')
