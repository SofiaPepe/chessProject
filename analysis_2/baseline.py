from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats

from common import fdr_bh, find_prepost_pairs, hedges_g, numeric_summary, to_numeric, write_workbook
from config import GROUP_COLUMN, GROUP_LABELS, ID_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "02_baseline"


def numeric_variables(df: pd.DataFrame) -> list[str]:
    paired_pre = {pair["pre_col"] for pair in find_prepost_pairs(df)}
    baseline_predictors = {
        column
        for column in df.columns
        if str(column).startswith(("ABAS_", "BRIEF_"))
    }
    variables = ["age", *sorted(paired_pre | baseline_predictors)]
    return [
        variable
        for variable in variables
        if variable in df and to_numeric(df[variable]).notna().sum() >= 4
    ]


def run(df: pd.DataFrame) -> dict:
    rows = []
    for variable in numeric_variables(df):
        experimental = to_numeric(df.loc[df[GROUP_COLUMN] == 1, variable]).dropna()
        control = to_numeric(df.loc[df[GROUP_COLUMN] == 2, variable]).dropna()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            welch_p = stats.ttest_ind(experimental, control, equal_var=False).pvalue if len(experimental) >= 2 and len(control) >= 2 else np.nan
            try:
                mann_p = stats.mannwhitneyu(experimental, control, alternative="two-sided").pvalue
            except ValueError:
                mann_p = np.nan
        rows.append(
            {
                "variable": variable,
                **numeric_summary(experimental, "experimental"),
                **numeric_summary(control, "control"),
                "mean_difference_exp_minus_ctrl": experimental.mean() - control.mean(),
                "hedges_g": hedges_g(experimental, control),
                "welch_p": welch_p,
                "mann_whitney_p": mann_p,
            }
        )
    numeric = fdr_bh(pd.DataFrame(rows), "welch_p")
    if not numeric.empty:
        numeric["significant_p05"] = numeric["welch_p"] < 0.05
        numeric["significant_fdr05"] = numeric["q_fdr_bh"] < 0.05
        numeric["meaningful_imbalance"] = numeric["hedges_g"].abs() >= 0.5
        numeric = numeric.sort_values(["significant_fdr05", "welch_p"], ascending=[False, True])

    categorical_rows = []
    count_rows = []
    for variable in ["sex", "class", "section", "hand", "semestre"]:
        if variable not in df:
            continue
        data = df[[GROUP_COLUMN, variable]].dropna()
        table = pd.crosstab(data[GROUP_COLUMN], data[variable])
        if table.shape[0] < 2 or table.shape[1] < 2:
            continue
        chi2, p_value, _, expected = stats.chi2_contingency(table)
        n = int(table.to_numpy().sum())
        min_dim = min(table.shape) - 1
        categorical_rows.append(
            {
                "variable": variable,
                "n": n,
                "levels": table.shape[1],
                "chi_square": chi2,
                "p_value": p_value,
                "cramers_v": np.sqrt(chi2 / (n * min_dim)) if n and min_dim else np.nan,
                "min_expected": expected.min(),
            }
        )
        for code, row in table.iterrows():
            for level, count in row.items():
                count_rows.append({"variable": variable, "group": GROUP_LABELS.get(code, code), "level": level, "count": int(count)})
    categorical = fdr_bh(pd.DataFrame(categorical_rows), "p_value") if categorical_rows else pd.DataFrame()
    counts = pd.DataFrame(count_rows)
    path = OUT_DIR / "baseline_checks.xlsx"
    write_workbook(path, {"numeric_baseline": numeric, "categorical_baseline": categorical, "categorical_counts": counts})
    return {"numeric": numeric, "categorical": categorical, "files": [path]}
