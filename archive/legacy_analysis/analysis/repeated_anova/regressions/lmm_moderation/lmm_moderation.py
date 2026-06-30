import sys
import os
import pandas as pd
import pingouin as pg
import openpyxl
import numpy as np
from openpyxl.styles import PatternFill
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[4] / "analysis" / "descriptives"))
from add_composites import build_composite_dataframe  # noqa: E402

# --- 1. CONFIGURATION ---
ROOT = Path(__file__).resolve().parents[4]
output_dir = ROOT / "output" / "repeated_anova" / "lmm_moderation"
output_dir.mkdir(parents=True, exist_ok=True)

df = build_composite_dataframe()
df.columns = df.columns.str.strip()

# Quick covariate cleanup (needed for statistical calculations)
if 'sesso' in df.columns: df['sesso'] = pd.factorize(df['sesso'])[0]
if 'età' in df.columns: df['età'] = pd.to_numeric(df['età'], errors='coerce')

# --- 2. MODERATION ANALYSIS FUNCTION ---
def run_moderation_analysis(moderatore, output_file):
    if moderatore not in df.columns:
        print(f"Skipping {moderatore}: non trovato nel file.")
        return

    lmm_list, ph_list, slopes_list = [], [], []
    
    # Automatic Pre/Post pair detection (raw and log)
    cols = list(df.columns)
    pairs = []
    for c in cols:
        if c.upper().endswith('_PRE_LN'):
            base = c[:-7]
            post = next((x for x in cols if x.upper() == (base + "_POST_LN").upper()), None)
            if post: pairs.append((base + "_ln", c, post))
        elif c.upper().endswith('_PRE') and not c.upper().endswith('_LN'):
            base = c[:-4]
            post = next((x for x in cols if x.upper() == (base + "_POST").upper()), None)
            if post: pairs.append((base, c, post))

    for base_name, col_pre, col_post in pairs:
        subset = ['ID', 'gruppo', col_pre, col_post, 'età', 'sesso', moderatore]
        temp_df = df[subset].dropna()
        if temp_df.empty or temp_df['gruppo'].nunique() < 2: continue
            
        long_df = pd.melt(temp_df, id_vars=['ID', 'gruppo', 'età', 'sesso', moderatore], 
                          value_vars=[col_pre, col_post], var_name='time', value_name='value')
        long_df['time_num'] = long_df['time'].str.upper().str.contains('POST').astype(int)
        
        # Centering and interactions for the model
        mod_mean, mod_std = long_df[moderatore].mean(), long_df[moderatore].std()
        long_df['interaction'] = long_df['gruppo'] * long_df['time_num']
        long_df['mod_gruppo'] = long_df['gruppo'] * long_df[moderatore]
        long_df['mod_time'] = long_df['time_num'] * long_df[moderatore]
        long_df['mod_3vie'] = long_df['gruppo'] * long_df['time_num'] * long_df[moderatore]
        
        try:
            # A. Linear regression (moderation)
            preds = ['gruppo', 'time_num', 'interaction', 'età', 'sesso', moderatore, 'mod_gruppo', 'mod_time', 'mod_3vie']
            lm = pg.linear_regression(long_df[preds], long_df['value'])
            lm.insert(0, 'Variable', base_name)
            lmm_list.append(lm)
            
            # B. Post-Hoc e Simple Slopes se l'interaction a 3 vie è significativa (p < 0.05)
            p_3vie = lm.loc[lm['names'] == 'mod_3vie', 'pval'].values[0]
            if p_3vie < 0.05:
                # Pairwise tests
                ph = pg.pairwise_tests(data=long_df, dv='value', within='time', between='gruppo', subject='ID', padjust='holm')
                ph.insert(0, 'Variable', base_name)
                ph_list.append(ph)
                
                # Simple Slopes (-1SD e +1SD)
                for label, val in [('Low (-1SD)', mod_mean - mod_std), ('High (+1SD)', mod_mean + mod_std)]:
                    long_df['mod_sh'] = long_df[moderatore] - val
                    long_df['int_sh'] = long_df['gruppo'] * long_df['time_num']
                    long_df['mod_g_sh'] = long_df['gruppo'] * long_df['mod_sh']
                    long_df['mod_t_sh'] = long_df['time_num'] * long_df['mod_sh']
                    long_df['mod_3v_sh'] = long_df['gruppo'] * long_df['time_num'] * long_df['mod_sh']
                    
                    preds_sh = ['gruppo', 'time_num', 'int_sh', 'età', 'sesso', 'mod_sh', 'mod_g_sh', 'mod_t_sh', 'mod_3v_sh']
                    lm_sh = pg.linear_regression(long_df[preds_sh], long_df['value'])
                    
                    slope_row = lm_sh.loc[lm_sh['names'] == 'int_sh'].copy()
                    slope_row.insert(0, 'Moderator_Level', label)
                    slope_row.insert(0, 'Variable', base_name)
                    slopes_list.append(slope_row)
        except: continue

    # Save Excel file with three sheets
    if lmm_list:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            pd.concat(lmm_list, ignore_index=True).to_excel(writer, sheet_name='LMM', index=False)
            if ph_list: pd.concat(ph_list, ignore_index=True).to_excel(writer, sheet_name='POST-HOC', index=False)
            if slopes_list: pd.concat(slopes_list, ignore_index=True).to_excel(writer, sheet_name='SIMPLE_SLOPES', index=False)
        
        # Conditional formatting (green for p < 0.05)
        wb = openpyxl.load_workbook(output_file)
        green = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')
        for sn in wb.sheetnames:
            ws = wb[sn]
            for col in ws.iter_cols(1, ws.max_column):
                header = str(col[0].value).lower()
                if any(x in header for x in ['pval', 'p-unc', 'p-corr', 'p_corr']):
                    for cell in col[1:]:
                        if cell.value is not None and isinstance(cell.value, (int, float)) and cell.value < 0.05:
                            cell.fill = green
        wb.save(output_file)
        print(f"Generated: {os.path.basename(output_file)}")

# --- 3. ESECUZIONE MASSIVA ---
# Define subscale names as they appear in the processed file
abas_subscales = ['amb', 'comscol', 'vitascuola', 'sal_sic', 'tempo_libero', 'curadisè', 'autocontrollo', 'soc']

# Main moderators

# Analysis for all requested BRIEF subscales
brief_subscales = [
    'BRIEF_ini', 'BRIEF_autom', 'BRI', 'BRIEF_shift', 'BRIEF_regem', 'ERI',
    'BRIEF_avvio', 'BRIEF_WM', 'BRIEF_pianific', 'BRIEF_monitoraggiodelcompito', 'BRIEF_organiz', 'CRI'
]
run_moderation_analysis('BRIEF_TOT', os.path.join(output_dir, 'moderation_analysis_BRIEF_TOT.xlsx'))
for sub in brief_subscales:
    out_file = os.path.join(output_dir, f'moderation_analysis_{sub}.xlsx')
    run_moderation_analysis(sub, out_file)
run_moderation_analysis('ABAS_TOT', os.path.join(output_dir, 'moderation_analysis_ABAS_TOT.xlsx'))
run_moderation_analysis('abas_suppongo_tot', os.path.join(output_dir, 'moderation_analysis_ABAS_SUPPONGO_TOT.xlsx'))

# Subscale moderators
for sub in abas_subscales:
    # Standard
    run_moderation_analysis(f'ABAS_{sub}', os.path.join(output_dir, f'moderation_analysis_ABAS_{sub}.xlsx'))
    # Assumed variants created by the other script as abas_s_...
    run_moderation_analysis(f'abas_s_{sub}', os.path.join(output_dir, f'moderation_analysis_abas_s_{sub}.xlsx'))

print("\nAnalysis completed successfully.")
