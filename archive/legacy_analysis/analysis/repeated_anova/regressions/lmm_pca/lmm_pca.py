import pandas as pd
import pingouin as pg
import os
from pathlib import Path

# --- CONFIG ---
ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = ROOT / "output" / "repeated_anova" / "lmm_pca"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
dir_base = str(OUTPUT_DIR)
file_path = ROOT / "output" / "pca" / "unified_pca_scores.xlsx"

# Loading (try different encodings if it is a CSV)
try:
    if str(file_path).endswith('.csv'):
        df = pd.read_csv(file_path, index_col=0, encoding='utf-8')
    else:
        df = pd.read_excel(file_path, index_col=0)
except UnicodeDecodeError:
    df = pd.read_csv(file_path, index_col=0, encoding='latin-1')

# --- ROBUST COLUMN-FINDING FUNCTION ---
def find_col(possible_names, df_cols):
    for name in possible_names:
        if name in df_cols:
            return name
    # Search by similarity if no exact column name is found
    for c in df_cols:
        for name in possible_names:
            if name.lower() in c.lower():
                return c
    return None

group_col = find_col(['gruppo', 'group', 'GROUP'], df.columns)
sex_col = find_col(['sesso', 'sex', 'SESSO'], df.columns)
age_col = find_col(['età', 'eta', 'et', 'ETÀ', 'ETA'], df.columns)

print(f"Identified columns: Gruppo={group_col}, Sesso={sex_col}, Età={age_col}")

if not all([group_col, sex_col, age_col]):
    print("ERROR: Could not find one of the required columns (gruppo, sesso, or età).")
    exit()

# Identify all PCs (columns ending in _pre)
pc_pre = [c for c in df.columns if c.endswith('_pre')]
pc_basenames = set([c.replace('_pre','') for c in pc_pre])

lmm_results = []
id_name = df.index.name if df.index.name else 'ID'

for base in pc_basenames:
    pre_col = base + '_pre'
    post_col = base + '_post'
    
    if pre_col not in df.columns or post_col not in df.columns:
        continue

    # Select data
    temp = df[[pre_col, post_col, group_col, age_col, sex_col]].copy()
    
    # Wide to long
    long_df = pd.melt(temp.reset_index(), 
                      id_vars=[id_name, group_col, age_col, sex_col],
                      value_vars=[pre_col, post_col], 
                      var_name='time', value_name='value')

    # Codifica time: pre=0, post=1
    long_df['time_num'] = long_df['time'].str.endswith('post').astype(int)
    
    # Ensure all model columns are numeric
    for col in [group_col, age_col, sex_col, 'value', 'time_num']:
        long_df[col] = pd.to_numeric(long_df[col], errors='coerce')

    # Compute interaction
    long_df['interaction'] = long_df[group_col] * long_df['time_num']

    # Remove rows with NaN
    predictors = [group_col, 'time_num', 'interaction', age_col, sex_col]
    long_df = long_df.dropna(subset=predictors + ['value'])

    if long_df.empty:
        continue

    try:
        # Regressione lineare
        lm = pg.linear_regression(long_df[predictors], long_df['value'])
        lm.insert(0, 'PC', base)
        lmm_results.append(lm)
    except Exception as e:
        print(f'Error for {base}: {e}')

# Save results
if lmm_results:
    final_res = pd.concat(lmm_results)
    out_path = os.path.join(dir_base, 'lmm_pca_results.xlsx')

    # Highlight significant p-values in green when jinja2 is available
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
        # Compute post-hoc tests and simple slopes for significant predictors
        posthoc_rows = []
        for _, row in final_res.iterrows():
            if 'p' in row and row['p'] < 0.05:
                pc = row['PC'] if 'PC' in row else None
                pred = row['names'] if 'names' in row else row['predictor'] if 'predictor' in row else None
                if pred in ['interaction', 'time_num', 'gruppo']:
                    pre_col = pc + '_pre'
                    post_col = pc + '_post'
                    if pre_col in df.columns and post_col in df.columns:
                        temp = df[[pre_col, post_col, group_col, age_col, sex_col]].copy()
                        long_df = pd.melt(temp.reset_index(), 
                                          id_vars=[df.index.name or 'ID', group_col, age_col, sex_col],
                                          value_vars=[pre_col, post_col], 
                                          var_name='time', value_name='value')
                        long_df['time_num'] = long_df['time'].str.endswith('post').astype(int)
                        long_df['interaction'] = long_df[group_col] * long_df['time_num']
                        predictors = [group_col, 'time_num', 'interaction', age_col, sex_col]
                        long_df = long_df.dropna(subset=predictors + ['value'])
                        try:
                            for g in long_df[group_col].unique():
                                slope = pg.linear_regression(long_df[long_df[group_col]==g][['time_num']],
                                                             long_df[long_df[group_col]==g]['value'])
                                slope['PC'] = pc
                                slope[group_col] = g
                                posthoc_rows.append(slope)
                            for g in long_df[group_col].unique():
                                pre = long_df[(long_df[group_col]==g)&(long_df['time_num']==0)]['value']
                                post = long_df[(long_df[group_col]==g)&(long_df['time_num']==1)]['value']
                                if len(pre)>1 and len(post)>1:
                                    ttest = pg.ttest(pre, post, paired=True)
                                    ttest['PC'] = pc
                                    ttest[group_col] = g
                                    posthoc_rows.append(ttest)
                        except Exception as e:
                            print(f'Post-hoc/simple-slope error for {pc}: {e}')
        if posthoc_rows:
            posthoc_df = pd.concat(posthoc_rows, ignore_index=True)
            posthoc_df.to_excel(writer, index=False, sheet_name='PostHoc_SimpleSlope')

    # Green p-value highlighting, matching lmm_all.py
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
    print(f'LMM PCA results saved to: {out_path} (with p-value highlighting and post-hoc results)')
else:
    print('No result computed. Check that PC_pre and PC_post columns exist.')
