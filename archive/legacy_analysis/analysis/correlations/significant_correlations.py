import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)


# --- IMPORTS AND DATA LOADING ---

import os
from pathlib import Path
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "correlations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
db_path = ROOT / "output" / "descriptives" / "final_chess_analysis.xlsx"
out_path = OUTPUT_DIR / "significant_correlations.xlsx"
df = pd.read_excel(db_path)

# --- GROUP DEFINITIONS ---
# GROUP 1: cognitive only
group_1 = [
    "CBT_F_SPAN_PRE", "CBT_B_SPAN_PRE", "TOL16_ACC_PRE", "TOL_VIO_REG_PRE", "WM_span_PRE", "WM_trial_PRE", "WM_acc_PRE",
    "PLANNING_span_PRE", "PLANNING_trial_PRE", "PLANNING_ACC_PRE", "PWM_ TRIAL_PRE", "PWM_ ACC_PRE",
    "tol_tp_pre", "tol_te_pre", "tol_rt_tot_pre", "planning_tr_tot_pre", "pwm_tr_tot_pre"
]
# GROUP 2: cognitive + ABAS
group_2 = group_1 + [
    "ABAS_amb", "ABAS_comscol", "ABAS_vitascuola", "ABAS_sal_sic", "ABAS_tempo_libero",
    "ABAS_curadisè", "ABAS_autocontrollo", "ABAS_soc"
]
# GROUP 3: cognitive + BRIEF
group_3 = group_1 + [
     "BRIEF_ini", "BRIEF_autom", "BRI", "BRIEF_shift", "BRIEF_regem", "ERI", "BRIEF_avvio",
    "BRIEF_WM", "BRIEF_pianific", "BRIEF_monitoraggiodelcompito", "BRIEF_organiz"
]

# GROUP 4: cognitive + new requested ABAS variables
group_4 = group_1 + [
    "ABAS_amb", "ABAS_comscol", "ABAS_vitascuola", "ABAS_sal_sic", "ABAS_tempo_libero",
    "ABAS_curadisè", "ABAS_autocontrollo", "ABAS_soc"
]
# 2. SELECT ALL NUMERIC VARIABLES
num_df = df.select_dtypes(include='number')

# 3. COMPUTE CORRELATIONS AND P-VALUES
corr = num_df.corr(method='pearson')
pval = num_df.corr(method=lambda x, y: pd.Series(x).corr(pd.Series(y), method='pearson', min_periods=1), min_periods=1)

# 4. EXTRACT SIGNIFICANT CORRELATIONS ONLY
from scipy.stats import pearsonr

results = []
cols = num_df.columns
for i in range(len(cols)):
    for j in range(i+1, len(cols)):
        x, y = cols[i], cols[j]
        try:
            r, p = pearsonr(num_df[x].dropna(), num_df[y].dropna())
            if pd.notnull(r) and pd.notnull(p) and p < 0.05:
                results.append({'Var1': x, 'Var2': y, 'r': r, 'p': p})
        except Exception as e:
            continue

# 5. SAVE SIGNIFICANT RESULTS ONLY
if results:
    df_results = pd.DataFrame(results)
    df_results.to_excel(out_path, index=False)

    # Highlight significant p-values (<0.05) in green
    import openpyxl
    from openpyxl.styles import PatternFill
    from openpyxl.formatting.rule import CellIsRule
    wb = openpyxl.load_workbook(out_path)
    ws = wb.active
    fill = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')  # light green
    # Find the p-value column
    for col in ws.iter_cols(1, ws.max_column):
        if col[0].value == 'p':
            col_letter = col[0].column_letter
            ws.conditional_formatting.add(f'{col_letter}2:{col_letter}{ws.max_row}',
                CellIsRule(operator='lessThan', formula=['0.05'], fill=fill))
            break
    wb.save(out_path)
else:
    print("No significant correlation found.")


# 6. CREATE AND SAVE A HEATMAP FOR EACH VARIABLE GROUP
def create_heatmap(group, file_name):
    # Listwise missing-data handling
    df_group = df[group].dropna()
    results = []
    cols = df_group.columns
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            x, y = cols[i], cols[j]
            try:
                r, p = pearsonr(df_group[x], df_group[y])
                if pd.notnull(r) and pd.notnull(p):
                    results.append({'Var1': x, 'Var2': y, 'r': r, 'p': p})
            except Exception:
                continue
    # Holm correction for p-values
    if results:
        pvals = [res['p'] for res in results]
        reject, pvals_corr, _, _ = multipletests(pvals, alpha=0.05, method='holm')
        for idx, res in enumerate(results):
            res['p_corr'] = pvals_corr[idx]
            res['sign'] = reject[idx]
        # Only correlations significant after correction
        filtered_results = [res for res in results if res['sign']]
        matrix_vars = group
        if filtered_results:
            sig_matrix = pd.DataFrame(float('nan'), index=matrix_vars, columns=matrix_vars)
            for res in filtered_results:
                sig_matrix.loc[res['Var1'], res['Var2']] = res['r']
                sig_matrix.loc[res['Var2'], res['Var1']] = res['r']
            plt.figure(figsize=(2+len(matrix_vars)*0.6, 2+len(matrix_vars)*0.6))
            sns.heatmap(sig_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1, linewidths=0.5, linecolor='gray', square=True, cbar_kws={"label": "r"})
            plt.title(f'Significant Pearson correlations (p < 0.05, Holm) - {file_name}')
            plt.tight_layout()
            img_path = OUTPUT_DIR / f'significant_correlations_{file_name}.png'
            plt.savefig(img_path, dpi=300)
            plt.close()
        else:
            print(f"No significant correlation among the selected variables for heatmap {file_name}.")
    else:
        print(f"No computable correlation for group {file_name}.")


# Generate the requested heatmaps

create_heatmap(group_1, "group1")
create_heatmap(group_2, "group2_abas")
create_heatmap(group_3, "group3_brief")
create_heatmap(group_4, "group4_abas_new")
