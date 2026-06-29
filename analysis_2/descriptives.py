from __future__ import annotations

import pandas as pd

from common import find_prepost_pairs, numeric_summary, to_numeric, write_workbook
from config import GROUP_COLUMN, GROUP_LABELS, ID_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "01_descriptives"


def numeric_columns(df: pd.DataFrame) -> list[str]:
    excluded = {ID_COLUMN, GROUP_COLUMN, "group_experimental"}
    columns = []
    for column in df.columns:
        if column in excluded:
            continue
        if str(column).startswith("MF_BEST_AVAILABLE_"):
            continue
        values = to_numeric(df[column])
        if values.notna().sum() >= 2:
            columns.append(column)
    return columns


def run(df: pd.DataFrame) -> dict:
    columns = numeric_columns(df)
    overall = pd.DataFrame(
        [{"variable": column, **numeric_summary(df[column])} for column in columns]
    )
    by_group_rows = []
    for column in columns:
        for code, label in GROUP_LABELS.items():
            values = df.loc[df[GROUP_COLUMN] == code, column]
            by_group_rows.append(
                {"variable": column, "group": label, **numeric_summary(values)}
            )
    by_group = pd.DataFrame(by_group_rows)
    missingness = pd.DataFrame(
        [
            {
                "variable": column,
                "n": int(df[column].notna().sum()),
                "missing": int(df[column].isna().sum()),
                "missing_pct": float(df[column].isna().mean() * 100),
                "unique_nonmissing": int(df[column].nunique(dropna=True)),
            }
            for column in df.columns
        ]
    ).sort_values(["missing_pct", "variable"], ascending=[False, True])

    composition_rows = []
    for variable in [GROUP_COLUMN, "group_label", "sex", "age", "class", "section"]:
        if variable not in df:
            continue
        counts = df[variable].value_counts(dropna=False)
        for level, count in counts.items():
            composition_rows.append(
                {
                    "variable": variable,
                    "level": level,
                    "count": int(count),
                    "percent": count / len(df) * 100,
                }
            )
    composition = pd.DataFrame(composition_rows)
    pairs = pd.DataFrame(find_prepost_pairs(df))
    path = OUT_DIR / "descriptive_statistics.xlsx"
    write_workbook(
        path,
        {
            "overall": overall,
            "by_group": by_group,
            "missingness": missingness,
            "sample_composition": composition,
            "prepost_dictionary": pairs,
        },
    )
    return {
        "overall": overall,
        "by_group": by_group,
        "missingness": missingness,
        "files": [path],
    }
