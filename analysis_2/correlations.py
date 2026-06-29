from __future__ import annotations

import itertools
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from common import fdr_bh, to_numeric, write_workbook
from config import GROUP_COLUMN, ID_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "03_correlations"


def select_columns(df: pd.DataFrame) -> list[str]:
    excluded = {ID_COLUMN, GROUP_COLUMN, "group_experimental"}
    columns = []
    for column in df.columns:
        if column in excluded:
            continue
        if str(column).startswith("MF_BEST_AVAILABLE_"):
            continue
        values = to_numeric(df[column])
        if values.notna().sum() >= 10 and values.nunique(dropna=True) > 1:
            columns.append(column)
    return columns


def run(df: pd.DataFrame) -> dict:
    columns = select_columns(df)
    numeric = df[columns].apply(to_numeric)
    pearson_matrix = numeric.corr(method="pearson")
    spearman_matrix = numeric.corr(method="spearman")
    rows = []
    for first, second in itertools.combinations(columns, 2):
        data = numeric[[first, second]].dropna()
        if len(data) < 10 or data[first].nunique() < 2 or data[second].nunique() < 2:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pearson_r, pearson_p = stats.pearsonr(data[first], data[second])
            spearman_r, spearman_p = stats.spearmanr(data[first], data[second])
        rows.append(
            {
                "variable_1": first,
                "variable_2": second,
                "n": len(data),
                "pearson_r": pearson_r,
                "pearson_p": pearson_p,
                "spearman_rho": spearman_r,
                "spearman_p": spearman_p,
            }
        )
    tidy = fdr_bh(pd.DataFrame(rows), "spearman_p", "spearman_q_fdr_bh")
    if not tidy.empty:
        tidy = fdr_bh(tidy, "pearson_p", "pearson_q_fdr_bh")
        tidy["spearman_significant_fdr05"] = tidy["spearman_q_fdr_bh"] < 0.05
        tidy["absolute_spearman_rho"] = tidy["spearman_rho"].abs()
        tidy = tidy.sort_values(["spearman_significant_fdr05", "absolute_spearman_rho"], ascending=[False, False])
    path = OUT_DIR / "correlations.xlsx"
    write_workbook(
        path,
        {
            "tidy_correlations": tidy,
            "spearman_matrix": spearman_matrix.reset_index(names="variable"),
            "pearson_matrix": pearson_matrix.reset_index(names="variable"),
            "included_variables": pd.DataFrame({"variable": columns}),
        },
    )
    return {"tidy": tidy, "files": [path]}
