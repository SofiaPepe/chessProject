
"""Convert the final chess analysis dataset from wide to long format."""

import os
import pandas as pd
import re
from pathlib import Path

# Load the Excel file
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "descriptives"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
file_path = OUTPUT_DIR / 'final_chess_analysis.xlsx'
df = pd.read_excel(file_path)

# Find the _PRE and _POST columns.
pre_cols = [col for col in df.columns if col.endswith('_PRE') or col.endswith('_pre')]
post_cols = [col for col in df.columns if col.endswith('_POST') or col.endswith('_post')]

# Find baseline columns without PRE/POST suffixes.
base_cols = [col for col in df.columns if not re.search(r'(_PRE|_pre|_POST|_post)$', col)]

# Keep variables that are present at both time points, in source-file order.
pre_base = [re.sub(r'(_PRE|_pre)$', '', col) for col in pre_cols]
post_base = [re.sub(r'(_POST|_post)$', '', col) for col in post_cols]
common_vars = []
for var in pre_base:
    if var in post_base:
        common_vars.append(var)

long_rows = []
for idx, row in df.iterrows():
    pre_data = {col: row[col] for col in base_cols}
    pre_data['time'] = 1
    for var in common_vars:
        pre_col = [c for c in pre_cols if re.sub(r'(_PRE|_pre)$', '', c) == var][0]
        pre_data[var] = row[pre_col]
    long_rows.append(pre_data)

    post_data = {col: row[col] for col in base_cols}
    post_data['time'] = 2
    for var in common_vars:
        post_col = [c for c in post_cols if re.sub(r'(_POST|_post)$', '', c) == var][0]
        post_data[var] = row[post_col]
    long_rows.append(post_data)

col_order = base_cols + ['time'] + common_vars
long_df = pd.DataFrame(long_rows)[col_order]

# Save both CSV and Excel outputs.
out_csv = OUTPUT_DIR / 'final_chess_analysis_long.csv'
out_xlsx = OUTPUT_DIR / 'final_chess_analysis_long.xlsx'
long_df.to_csv(out_csv, index=False)
long_df.to_excel(out_xlsx, index=False)
print('Long file created in both CSV and Excel.')
