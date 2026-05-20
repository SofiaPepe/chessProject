from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, PatternFill
from scipy import stats

from add_composites import DB_PATH, build_composite_dataframe


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "descriptives"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INPUT_PATH = DB_PATH
OUTPUT_PATH = OUTPUT_DIR / "baseline_checks.xlsx"

GROUP_COLUMN = "group"
GROUP_LABELS = {
    1: "experimental",
    2: "control",
}

CATEGORICAL_CANDIDATES = [
    "sex",
    "class",
    "section",
    "hand",
    "semestre",
    "age_semester_group",
]

BASELINE_PREFIXES = (
    "ABAS_",
    "BRIEF_",
)


def to_numeric(series: pd.Series) -> pd.Series:
    """Coerce numeric-looking columns, accepting comma decimals."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = series.astype(str).str.replace(",", ".", regex=False)
    cleaned = cleaned.replace({"nan": np.nan, "None": np.nan, "": np.nan})
    return pd.to_numeric(cleaned, errors="coerce")


def group_values(df: pd.DataFrame, variable: str) -> tuple[pd.Series, pd.Series]:
    data = df[[GROUP_COLUMN, variable]].copy()
    data[variable] = to_numeric(data[variable])
    experimental = data.loc[data[GROUP_COLUMN] == 1, variable].dropna()
    control = data.loc[data[GROUP_COLUMN] == 2, variable].dropna()
    return experimental, control


def describe(values: pd.Series, prefix: str) -> dict:
    return {
        f"{prefix}_n": int(values.count()),
        f"{prefix}_mean": values.mean(),
        f"{prefix}_sd": values.std(ddof=1),
        f"{prefix}_median": values.median(),
        f"{prefix}_q1": values.quantile(0.25),
        f"{prefix}_q3": values.quantile(0.75),
        f"{prefix}_min": values.min(),
        f"{prefix}_max": values.max(),
    }


def hedges_g(experimental: pd.Series, control: pd.Series) -> float:
    n_exp = experimental.count()
    n_ctrl = control.count()
    if n_exp < 2 or n_ctrl < 2:
        return np.nan

    var_exp = experimental.var(ddof=1)
    var_ctrl = control.var(ddof=1)
    pooled_den = n_exp + n_ctrl - 2
    if pooled_den <= 0:
        return np.nan

    pooled_sd = np.sqrt(((n_exp - 1) * var_exp + (n_ctrl - 1) * var_ctrl) / pooled_den)
    if pooled_sd == 0 or np.isnan(pooled_sd):
        return np.nan

    cohen_d = (experimental.mean() - control.mean()) / pooled_sd
    correction = 1 - (3 / (4 * (n_exp + n_ctrl) - 9))
    return cohen_d * correction


def mann_whitney_p(experimental: pd.Series, control: pd.Series) -> float:
    if experimental.empty or control.empty:
        return np.nan
    try:
        return stats.mannwhitneyu(experimental, control, alternative="two-sided").pvalue
    except ValueError:
        return np.nan


def welch_p(experimental: pd.Series, control: pd.Series) -> float:
    if experimental.count() < 2 or control.count() < 2:
        return np.nan
    if experimental.nunique() <= 1 and control.nunique() <= 1:
        return np.nan
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        return stats.ttest_ind(experimental, control, equal_var=False, nan_policy="omit").pvalue


def bh_fdr(p_values: pd.Series) -> pd.Series:
    """Benjamini-Hochberg FDR correction without extra dependencies."""
    p = pd.to_numeric(p_values, errors="coerce")
    q = pd.Series(np.nan, index=p.index, dtype=float)
    valid = p.dropna().sort_values(ascending=True)
    m = len(valid)
    if m == 0:
        return q

    adjusted = valid * m / np.arange(1, m + 1)
    adjusted = adjusted.iloc[::-1].cummin().iloc[::-1].clip(upper=1)
    q.loc[adjusted.index] = adjusted
    return q


def variable_section(column: str) -> str:
    upper_col = column.upper()
    if column in {"age", "eta", "età", "etÃ "}:
        return "demographics"
    if upper_col.endswith("_PRE") or column.endswith("_pre"):
        return "pre_score"
    if column.startswith(BASELINE_PREFIXES):
        return "baseline_predictor"
    return "other"


def select_numeric_variables(df: pd.DataFrame) -> list[str]:
    variables = []
    for column in df.columns:
        if column in {GROUP_COLUMN, "ID"}:
            continue

        section = variable_section(column)
        if section == "other":
            continue

        numeric = to_numeric(df[column])
        if numeric.notna().sum() == 0:
            continue
        variables.append(column)
    return variables


def select_categorical_variables(df: pd.DataFrame) -> list[str]:
    variables = []
    for column in CATEGORICAL_CANDIDATES:
        if column not in df.columns:
            continue
        values = df[column].dropna()
        if 2 <= values.nunique() <= 20:
            variables.append(column)
    return variables


def numeric_baseline_table(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    rows = []
    for variable in variables:
        experimental, control = group_values(df, variable)
        row = {
            "variable": variable,
            "section": variable_section(variable),
            "direction": "experimental_minus_control",
            **describe(experimental, "experimental"),
            **describe(control, "control"),
            "mean_difference": experimental.mean() - control.mean(),
            "hedges_g": hedges_g(experimental, control),
            "welch_p": welch_p(experimental, control),
            "mann_whitney_p": mann_whitney_p(experimental, control),
        }
        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result["welch_q_fdr"] = bh_fdr(result["welch_p"])
    result["low_n_flag"] = (result["experimental_n"] < 10) | (result["control_n"] < 10)
    result["baseline_difference_flag"] = (
        (result["welch_p"] < 0.05)
        | (result["mann_whitney_p"] < 0.05)
        | ((result["hedges_g"].abs() >= 0.50) & ~result["low_n_flag"])
    )
    return result.sort_values(["baseline_difference_flag", "section", "variable"], ascending=[False, True, True])


def categorical_tables(df: pd.DataFrame, variables: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    count_rows = []

    for variable in variables:
        data = df[[GROUP_COLUMN, variable]].dropna().copy()
        if data.empty:
            continue

        table = pd.crosstab(data[GROUP_COLUMN], data[variable])
        if len(table.index) < 2 or len(table.columns) < 2:
            continue

        chi2, chi_p, _, expected = stats.chi2_contingency(table)
        n = table.to_numpy().sum()
        min_dim = min(table.shape[0] - 1, table.shape[1] - 1)
        cramers_v = np.sqrt(chi2 / (n * min_dim)) if n > 0 and min_dim > 0 else np.nan

        fisher_p = np.nan
        if table.shape == (2, 2):
            try:
                fisher_p = stats.fisher_exact(table.to_numpy()).pvalue
            except ValueError:
                fisher_p = np.nan

        summary_rows.append(
            {
                "variable": variable,
                "n": int(n),
                "levels": ", ".join(map(str, table.columns.tolist())),
                "chi_square_p": chi_p,
                "fisher_p_2x2": fisher_p,
                "min_expected_count": float(np.min(expected)),
                "cramers_v": cramers_v,
                "baseline_difference_flag": (chi_p < 0.05) or (not np.isnan(fisher_p) and fisher_p < 0.05),
            }
        )

        for group_code, row in table.iterrows():
            group_n = row.sum()
            for level, count in row.items():
                count_rows.append(
                    {
                        "variable": variable,
                        "group": GROUP_LABELS.get(group_code, str(group_code)),
                        "level": level,
                        "count": int(count),
                        "percent_within_group": (count / group_n * 100) if group_n else np.nan,
                    }
                )

    summary = pd.DataFrame(summary_rows)
    counts = pd.DataFrame(count_rows)
    if not summary.empty:
        summary["chi_square_q_fdr"] = bh_fdr(summary["chi_square_p"])
        summary = summary.sort_values(["baseline_difference_flag", "variable"], ascending=[False, True])
    return summary, counts


def write_readme(
    writer: pd.ExcelWriter,
    numeric_variables: list[str],
    categorical_variables: list[str],
    output_path: Path,
) -> None:
    notes = pd.DataFrame(
        [
            {"item": "input", "value": str(INPUT_PATH.relative_to(ROOT))},
            {"item": "output", "value": str(output_path.relative_to(ROOT))},
            {"item": "database_policy", "value": "data/FINAL_DATABASE.xlsx is the only database; composites are in-memory only"},
            {"item": "group_coding", "value": "1 = experimental; 2 = control"},
            {"item": "numeric_test", "value": "Welch independent-samples t-test plus Mann-Whitney U"},
            {"item": "effect_size", "value": "Hedges g, experimental minus control"},
            {"item": "flag_rule", "value": "p < .05 in either test, or absolute Hedges g >= 0.50"},
            {"item": "numeric_variables_n", "value": len(numeric_variables)},
            {"item": "categorical_variables_n", "value": len(categorical_variables)},
        ]
    )
    notes.to_excel(writer, sheet_name="readme", index=False)


def format_workbook(path: Path) -> None:
    wb = load_workbook(path)
    header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
    significant_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    flag_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        for column_cells in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 45)

        headers = {cell.value: cell.column_letter for cell in ws[1]}
        for p_col in ["welch_p", "mann_whitney_p", "chi_square_p", "fisher_p_2x2"]:
            if p_col in headers and ws.max_row > 1:
                col = headers[p_col]
                ws.conditional_formatting.add(
                    f"{col}2:{col}{ws.max_row}",
                    CellIsRule(operator="lessThan", formula=["0.05"], fill=significant_fill),
                )
        if "baseline_difference_flag" in headers and ws.max_row > 1:
            col = headers["baseline_difference_flag"]
            ws.conditional_formatting.add(
                f"{col}2:{col}{ws.max_row}",
                CellIsRule(operator="equal", formula=["TRUE"], fill=flag_fill),
            )

    wb.save(path)


def write_results(
    output_path: Path,
    numeric_variables: list[str],
    categorical_variables: list[str],
    numeric_results: pd.DataFrame,
    categorical_summary: pd.DataFrame,
    categorical_counts: pd.DataFrame,
    included_variables: pd.DataFrame,
) -> Path:
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            write_readme(writer, numeric_variables, categorical_variables, output_path)
            numeric_results.to_excel(writer, sheet_name="numeric_baseline", index=False)
            categorical_summary.to_excel(writer, sheet_name="categorical_baseline", index=False)
            categorical_counts.to_excel(writer, sheet_name="categorical_counts", index=False)
            included_variables.to_excel(writer, sheet_name="included_variables", index=False)
        return output_path
    except PermissionError:
        fallback_path = output_path.with_name(f"{output_path.stem}_updated{output_path.suffix}")
        with pd.ExcelWriter(fallback_path, engine="openpyxl") as writer:
            write_readme(writer, numeric_variables, categorical_variables, fallback_path)
            numeric_results.to_excel(writer, sheet_name="numeric_baseline", index=False)
            categorical_summary.to_excel(writer, sheet_name="categorical_baseline", index=False)
            categorical_counts.to_excel(writer, sheet_name="categorical_counts", index=False)
            included_variables.to_excel(writer, sheet_name="included_variables", index=False)
        return fallback_path


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Official database not found: {INPUT_PATH}."
        )

    df = build_composite_dataframe()

    if GROUP_COLUMN not in df.columns:
        raise ValueError(f"Required group column not found: {GROUP_COLUMN}")

    df[GROUP_COLUMN] = pd.to_numeric(df[GROUP_COLUMN], errors="coerce")
    df = df[df[GROUP_COLUMN].isin(GROUP_LABELS.keys())].copy()

    numeric_variables = select_numeric_variables(df)
    categorical_variables = select_categorical_variables(df)

    numeric_results = numeric_baseline_table(df, numeric_variables)
    categorical_summary, categorical_counts = categorical_tables(df, categorical_variables)
    included_variables = pd.DataFrame(
        [{"variable": variable, "type": "numeric", "section": variable_section(variable)} for variable in numeric_variables]
        + [{"variable": variable, "type": "categorical", "section": "demographics"} for variable in categorical_variables]
    )

    output_path = write_results(
        OUTPUT_PATH,
        numeric_variables,
        categorical_variables,
        numeric_results,
        categorical_summary,
        categorical_counts,
        included_variables,
    )

    format_workbook(output_path)

    numeric_flags = int(numeric_results["baseline_difference_flag"].sum()) if not numeric_results.empty else 0
    categorical_flags = (
        int(categorical_summary["baseline_difference_flag"].sum()) if not categorical_summary.empty else 0
    )

    print(f"Baseline checks saved to: {output_path}")
    print(f"Numeric variables checked: {len(numeric_variables)}; flagged: {numeric_flags}")
    print(f"Categorical variables checked: {len(categorical_variables)}; flagged: {categorical_flags}")


if __name__ == "__main__":
    main()
