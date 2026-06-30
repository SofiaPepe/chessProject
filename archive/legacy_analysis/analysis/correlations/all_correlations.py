import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

import os
from pathlib import Path
import pandas as pd
from scipy.stats import pearsonr

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "correlations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
db_path = ROOT / "output" / "descriptives" / "final_chess_analysis.xlsx"
out_path = OUTPUT_DIR / "all_correlations.xlsx"
df = pd.read_excel(db_path)


# Convert non-numeric columns to numeric values where possible
df_encoded = df.copy()
for col in df.columns:
    if df[col].dtype == 'object':
        try:
            df_encoded[col] = pd.to_numeric(df[col], errors='coerce')
        except Exception:
            df_encoded[col] = df[col].astype('category').cat.codes

# Compute all correlations and p-values
results = []
cols = df_encoded.columns
for i in range(len(cols)):
    for j in range(i+1, len(cols)):
        x, y = cols[i], cols[j]
        try:
            r, p = pearsonr(df_encoded[x].dropna(), df_encoded[y].dropna())
            if pd.notnull(r) and pd.notnull(p):
                results.append({'Var1': x, 'Var2': y, 'r': r, 'p': p})
        except Exception:
            continue

# Save all correlations, significant and non-significant
if results:
    df_results = pd.DataFrame(results)
    df_results.to_excel(out_path, index=False)
    print(f"File saved: {out_path}")
else:
    print("No computable correlation.")
