import pandas as pd
import pingouin as pg
import os

# --- CONFIG ---
dir_base = os.path.dirname(os.path.abspath(__file__))
# Cambia il nome del file se necessario (es. .csv o .xlsx)
file_path = os.path.join(dir_base, '../pca/scores_pca_unificato.xlsx')

# Caricamento (prova diverse codifiche se è un CSV)
try:
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path, index_col=0, encoding='utf-8')
    else:
        df = pd.read_excel(file_path, index_col=0)
except UnicodeDecodeError:
    df = pd.read_csv(file_path, index_col=0, encoding='latin-1')

# --- FUNZIONE ROBUSTA PER TROVARE LE COLONNE ---
def find_col(possible_names, df_cols):
    for name in possible_names:
        if name in df_cols:
            return name
    # Cerca per somiglianza se non trova il nome esatto
    for c in df_cols:
        for name in possible_names:
            if name.lower() in c.lower():
                return c
    return None

group_col = find_col(['gruppo', 'group', 'GRUPPO'], df.columns)
sex_col = find_col(['sesso', 'sex', 'SESSO'], df.columns)
age_col = find_col(['età', 'eta', 'et', 'ETÀ', 'ETA'], df.columns)

print(f"Colonne identificate: Gruppo={group_col}, Sesso={sex_col}, Età={age_col}")

if not all([group_col, sex_col, age_col]):
    print("ERRORE: Impossibile trovare una delle colonne necessarie (gruppo, sesso o età).")
    exit()

# Identifica tutte le PC (colonne che finiscono con _pre)
pc_pre = [c for c in df.columns if c.endswith('_pre')]
pc_basenames = set([c.replace('_pre','') for c in pc_pre])

lmm_results = []
id_name = df.index.name if df.index.name else 'ID'

for base in pc_basenames:
    pre_col = base + '_pre'
    post_col = base + '_post'
    
    if pre_col not in df.columns or post_col not in df.columns:
        continue

    # Seleziona dati
    temp = df[[pre_col, post_col, group_col, age_col, sex_col]].copy()
    
    # Wide to long
    long_df = pd.melt(temp.reset_index(), 
                      id_vars=[id_name, group_col, age_col, sex_col],
                      value_vars=[pre_col, post_col], 
                      var_name='tempo', value_name='valore')

    # Codifica tempo: pre=0, post=1
    long_df['tempo_num'] = long_df['tempo'].str.endswith('post').astype(int)
    
    # Assicuriamoci che tutto sia numerico (dato che hai già messo 0, 1, 2)
    for col in [group_col, age_col, sex_col, 'valore', 'tempo_num']:
        long_df[col] = pd.to_numeric(long_df[col], errors='coerce')

    # Calcola interazione
    long_df['interazione'] = long_df[group_col] * long_df['tempo_num']

    # Rimuovi righe con NaN
    predictors = [group_col, 'tempo_num', 'interazione', age_col, sex_col]
    long_df = long_df.dropna(subset=predictors + ['valore'])

    if long_df.empty:
        continue

    try:
        # Regressione lineare
        lm = pg.linear_regression(long_df[predictors], long_df['valore'])
        lm.insert(0, 'PC', base)
        lmm_results.append(lm)
    except Exception as e:
        print(f'Errore su {base}: {e}')

# Salva risultati
if lmm_results:
    final_res = pd.concat(lmm_results)
    out_path = os.path.join(dir_base, 'lmm_pca_risultati.xlsx')

    # Evidenziazione p-value significativi in verde, se jinja2 è disponibile
    def highlight_significant(val):
        try:
            if float(val) < 0.05:
                return 'background-color: lightgreen'
        except:
            pass
        return ''

    try:
        import jinja2
        style_ok = True
    except ImportError:
        style_ok = False

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        final_res.to_excel(writer, index=False, sheet_name='LMM')
        # Calcola post-hoc e simple slope per predittori significativi
        posthoc_rows = []
        for _, row in final_res.iterrows():
            if 'p' in row and row['p'] < 0.05:
                pc = row['PC'] if 'PC' in row else None
                pred = row['names'] if 'names' in row else row['predictor'] if 'predictor' in row else None
                if pred in ['interazione', 'tempo_num', 'gruppo']:
                    pre_col = pc + '_pre'
                    post_col = pc + '_post'
                    if pre_col in df.columns and post_col in df.columns:
                        temp = df[[pre_col, post_col, group_col, age_col, sex_col]].copy()
                        long_df = pd.melt(temp.reset_index(), 
                                          id_vars=[df.index.name or 'ID', group_col, age_col, sex_col],
                                          value_vars=[pre_col, post_col], 
                                          var_name='tempo', value_name='valore')
                        long_df['tempo_num'] = long_df['tempo'].str.endswith('post').astype(int)
                        long_df['interazione'] = long_df[group_col] * long_df['tempo_num']
                        predictors = [group_col, 'tempo_num', 'interazione', age_col, sex_col]
                        long_df = long_df.dropna(subset=predictors + ['valore'])
                        try:
                            for g in long_df[group_col].unique():
                                slope = pg.linear_regression(long_df[long_df[group_col]==g][['tempo_num']],
                                                             long_df[long_df[group_col]==g]['valore'])
                                slope['PC'] = pc
                                slope[group_col] = g
                                posthoc_rows.append(slope)
                            for g in long_df[group_col].unique():
                                pre = long_df[(long_df[group_col]==g)&(long_df['tempo_num']==0)]['valore']
                                post = long_df[(long_df[group_col]==g)&(long_df['tempo_num']==1)]['valore']
                                if len(pre)>1 and len(post)>1:
                                    ttest = pg.ttest(pre, post, paired=True)
                                    ttest['PC'] = pc
                                    ttest[group_col] = g
                                    posthoc_rows.append(ttest)
                        except Exception as e:
                            print(f'Errore post-hoc/simple slope per {pc}: {e}')
        if posthoc_rows:
            posthoc_df = pd.concat(posthoc_rows, ignore_index=True)
            posthoc_df.to_excel(writer, index=False, sheet_name='PostHoc_SimpleSlope')

    # Evidenziazione verde dei p-value (come lmm_all.py)
    import openpyxl
    from openpyxl.styles import PatternFill
    from openpyxl.formatting.rule import CellIsRule
    wb = openpyxl.load_workbook(out_path)
    green_fill = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')
    p_targets = ['p', 'pval', 'p-unc', 'p-corr', 'p-adj']
    for sheetname in wb.sheetnames:
        ws = wb[sheetname]
        for col in ws.iter_cols(1, ws.max_column):
            header = str(col[0].value).lower()
            if any(x in header for x in p_targets):
                col_let = col[0].column_letter
                ws.conditional_formatting.add(f'{col_let}2:{col_let}{ws.max_row}',
                    CellIsRule(operator='lessThan', formula=['0.05'], fill=green_fill))
                for cell in col[1:]:
                    cell.number_format = '0.00000'
    wb.save(out_path)
    print(f'Risultati LMM PCA salvati in: {out_path} (con evidenziazione p-value e post-hoc)')
else:
    print('Nessun risultato calcolato. Controlla che le colonne PC_pre e PC_post esistano.')