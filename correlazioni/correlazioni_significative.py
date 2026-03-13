import pandas as pd
import os

dir_base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(dir_base, '../descrittive/database_compositi.xlsx')
out_path = os.path.join(dir_base, 'correlazioni_significative.xlsx')

# 1. CARICA DATABASE

df = pd.read_excel(db_path)


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
