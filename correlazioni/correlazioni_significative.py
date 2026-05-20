import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)


# --- IMPORT E CARICAMENTO DATI ---

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.stats.multitest import multipletests

dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/analisi_scacchi_definitive.csv')
out_path = os.path.join(dir_base, 'correlazioni_significative.xlsx')
df = pd.read_csv(db_path)

# --- DEFINIZIONE GRUPPI ---
# GRUPPO 1: solo cognitive
gruppo_1 = [
    "CBT_F_SPAN_PRE", "CBT_B_SPAN_PRE", "TOL16_ACC_PRE", "TOL_VIO_REG_PRE", "WM_span_PRE", "WM_trial_PRE", "WM_acc_PRE",
    "PLANNING_span_PRE", "PLANNING_trial_PRE", "PLANNING_ACC_PRE", "PWM_ TRIAL_PRE", "PWM_ ACC_PRE",
    "tol_tp_pre", "tol_te_pre", "tol_rt_tot_pre", "planning_tr_tot_pre", "pwm_tr_tot_pre"
]
# GRUPPO 2: cognitive + ABAS
gruppo_2 = gruppo_1 + [
    "ABAS_amb", "ABAS_comscol", "ABAS_vitascuola", "ABAS_sal_sic", "ABAS_tempo_libero",
    "ABAS_curadisè", "ABAS_autocontrollo", "ABAS_soc"
]
# GRUPPO 3: cognitive + BRIEF
gruppo_3 = gruppo_1 + [
     "BRIEF_ini", "BRIEF_autom", "BRI", "BRIEF_shift", "BRIEF_regem", "ERI", "BRIEF_avvio",
    "BRIEF_WM", "BRIEF_pianific", "BRIEF_monitoraggiodelcompito", "BRIEF_organiz"
]

# GRUPPO 4: cognitive + nuove variabili ABAS richieste
gruppo_4 = gruppo_1 + [
    "ABAS_amb", "ABAS_comscol", "ABAS_vitascuola", "ABAS_sal_sic", "ABAS_tempo_libero",
    "ABAS_curadisè", "ABAS_autocontrollo", "ABAS_soc"
]
# 2. SELEZIONA TUTTE LE VARIABILI NUMERICHE
num_df = df.select_dtypes(include='number')

# 3. CALCOLA CORRELAZIONI E P-VALUE
corr = num_df.corr(method='pearson')
pval = num_df.corr(method=lambda x, y: pd.Series(x).corr(pd.Series(y), method='pearson', min_periods=1), min_periods=1)

# 4. ESTRAI SOLO LE CORRELAZIONI SIGNIFICATIVE
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

# 5. SALVA SOLO LE SIGNIFICATIVE
if results:
    df_results = pd.DataFrame(results)
    df_results.to_excel(out_path, index=False)

    # Evidenzia i p-value significativi (<0.05) in verde
    import openpyxl
    from openpyxl.styles import PatternFill
    from openpyxl.formatting.rule import CellIsRule
    wb = openpyxl.load_workbook(out_path)
    ws = wb.active
    fill = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')  # verde chiaro
    # Trova la colonna del p-value
    for col in ws.iter_cols(1, ws.max_column):
        if col[0].value == 'p':
            col_letter = col[0].column_letter
            ws.conditional_formatting.add(f'{col_letter}2:{col_letter}{ws.max_row}',
                CellIsRule(operator='lessThan', formula=['0.05'], fill=fill))
            break
    wb.save(out_path)
else:
    print("Nessuna correlazione significativa trovata.")


# 6. CREA E SALVA UNA HEATMAP PER OGNI GRUPPO DI VARIABILI
def crea_heatmap(gruppo, nome_file):
    # Gestione dati mancanti listwise
    df_group = df[gruppo].dropna()
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
    # Correzione di Holm sui p-value
    if results:
        pvals = [res['p'] for res in results]
        reject, pvals_corr, _, _ = multipletests(pvals, alpha=0.05, method='holm')
        for idx, res in enumerate(results):
            res['p_corr'] = pvals_corr[idx]
            res['sign'] = reject[idx]
        # Solo correlazioni significative dopo correzione
        filtered_results = [res for res in results if res['sign']]
        matrix_vars = gruppo
        if filtered_results:
            sig_matrix = pd.DataFrame(float('nan'), index=matrix_vars, columns=matrix_vars)
            for res in filtered_results:
                sig_matrix.loc[res['Var1'], res['Var2']] = res['r']
                sig_matrix.loc[res['Var2'], res['Var1']] = res['r']
            plt.figure(figsize=(2+len(matrix_vars)*0.6, 2+len(matrix_vars)*0.6))
            sns.heatmap(sig_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1, linewidths=0.5, linecolor='gray', square=True, cbar_kws={"label": "r"})
            plt.title(f'Correlazioni Pearson significative (p < 0.05, Holm) - {nome_file}')
            plt.tight_layout()
            img_path = os.path.join(dir_base, f'correlazioni_significative_{nome_file}.png')
            plt.savefig(img_path, dpi=300)
            plt.close()
        else:
            print(f"Nessuna correlazione significativa tra le variabili selezionate per la heatmap {nome_file}.")
    else:
        print(f"Nessuna correlazione calcolabile per il gruppo {nome_file}.")


# Genera le tre heatmap richieste

crea_heatmap(gruppo_1, "gruppo1")
crea_heatmap(gruppo_2, "gruppo2_abas")
crea_heatmap(gruppo_3, "gruppo3_brief")
crea_heatmap(gruppo_4, "gruppo4_abas_nuove")
