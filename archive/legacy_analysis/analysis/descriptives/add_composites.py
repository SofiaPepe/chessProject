from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from pandas.errors import PerformanceWarning


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

DB_PATH = DATA_DIR / "FINAL_DATABASE.xlsx"


COLUMN_RENAMES = {
    "PWM_ MATT_MIN_PRE": "PWM_MATT_MIN_PRE",
}

ABAS_SUBSCALES = {
    "communication": ("ABAS_comm_use", "ABAS_comm_use_supp"),
    "functional_academics": ("ABAS_fun_acc", "ABAS_fun_acc_suppongo"),
    "school_living": ("ABAS_school_liv", "ABAS_school_liv_suppongo"),
    "health_safety": ("ABAS_Health_saf_sic", "ABAS_Health_saf_suppongo"),
    "leisure": ("ABAS_Leisure", "ABAS_Leisure_suppongo"),
    "self_care": ("ABAS_Selfcare", "ABAS_Selfcare_suppongo"),
    "self_direction": ("ABAS_Selfdirection", "ABAS_Selfdirection_suppongo"),
    "social": ("ABAS_soc", "ABAS_soc_suppongo"),
}

BRIEF_SUBSCALES = [
    "BRIEF_Inhibit",
    "BRIEF_SelfMonitor",
    "BRIEF_shift",
    "BRIEF_Em_Con",
    "BRIEF_Initiate",
    "BRIEF_wm",
    "BRIEF_plann",
    "BRIEF_TaskMonitor",
    "BRIEF_OrganizMaterial",
]

LOG_VARIABLES = [
    "TOL_TP_PRE",
    "TOL_TP_POST",
    "TOL_TE_PRE",
    "TOL_TE_POST",
    "TOL_TR_PRE",
    "TOL_TR_POST",
    "PLANNING_TP_PRE",
    "PLANNING_TP_POST",
    "PLANNING_TE_PRE",
    "PLANNING_TE_POST",
    "PLANNING_TR_PRE",
    "PWM_TP_PRE",
    "PWM_TP_POST",
    "PWM_TE_PRE",
    "PWM_TE_POST",
    "PWM_TR_PRE",
]


def to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = series.astype(str).str.replace(",", ".", regex=False)
    cleaned = cleaned.replace({"nan": np.nan, "None": np.nan, "": np.nan})
    return pd.to_numeric(cleaned, errors="coerce")


def compact_name(value: str) -> str:
    return " ".join(str(value).strip().split()).lower()


def build_column_renames(columns: pd.Index) -> dict[str, str]:
    renames = {old: new for old, new in COLUMN_RENAMES.items() if old in columns}

    for column in columns:
        compact = compact_name(column)
        if compact.startswith("eta_2") and "gruppo 1" in compact and "secondo semestre" in compact:
            renames[column] = "age_semester_group"

    return renames


def add_if_columns_exist(df: pd.DataFrame, output_col: str, input_cols: list[str]) -> None:
    existing = [col for col in input_cols if col in df.columns]
    if existing:
        df[output_col] = df[existing].apply(to_numeric).sum(axis=1, min_count=1)


def positive_difference(
    df: pd.DataFrame,
    output_col: str,
    observed_col: str,
    minimum_col: str,
    valid_min: float = 0,
    valid_max: float = 50,
) -> None:
    if observed_col not in df.columns or minimum_col not in df.columns:
        return
    observed = to_numeric(df[observed_col])
    minimum = to_numeric(df[minimum_col])
    raw = observed - minimum
    df[output_col] = raw.where(raw.between(valid_min, valid_max))


def bounded_percent(series: pd.Series, minimum: float, maximum: float, higher_better: bool = True) -> pd.Series:
    values = to_numeric(series)
    values = values.where(values.between(minimum, maximum))
    if maximum == minimum:
        return pd.Series(np.nan, index=series.index, dtype=float)
    if higher_better:
        return ((values - minimum) / (maximum - minimum)) * 100
    return ((maximum - values) / (maximum - minimum)) * 100


def add_planning_composite(
    df: pd.DataFrame,
    output_col: str,
    accuracy_col: str,
    tiles_extra_col: str,
    accuracy_max: float = 16,
    tiles_extra_max: float = 50,
) -> None:
    if accuracy_col not in df.columns or tiles_extra_col not in df.columns:
        return

    accuracy_pct = bounded_percent(df[accuracy_col], 0, accuracy_max, higher_better=True)
    tiles_quality_pct = bounded_percent(df[tiles_extra_col], 0, tiles_extra_max, higher_better=False)
    df[output_col] = pd.concat([accuracy_pct, tiles_quality_pct], axis=1).mean(axis=1, skipna=False)


def build_composite_dataframe() -> pd.DataFrame:
    warnings.filterwarnings("ignore", category=PerformanceWarning)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Official database not found: {DB_PATH}")

    df = pd.read_excel(DB_PATH)
    df.columns = df.columns.str.strip()
    df = df.rename(columns=build_column_renames(df.columns))

    abas_standard_cols = []
    abas_assumed_cols = []
    for subscale, (standard_col, supplement_col) in ABAS_SUBSCALES.items():
        if standard_col in df.columns:
            abas_standard_cols.append(standard_col)
        if standard_col in df.columns and supplement_col in df.columns:
            assumed_col = f"ABAS_assumed_{subscale}"
            df[assumed_col] = df[[standard_col, supplement_col]].apply(to_numeric).sum(axis=1, min_count=1)
            abas_assumed_cols.append(assumed_col)

    add_if_columns_exist(df, "ABAS_TOT", abas_standard_cols)
    add_if_columns_exist(df, "ABAS_assumed_total", abas_assumed_cols)

    add_if_columns_exist(df, "BRIEF_TOT", BRIEF_SUBSCALES)

    positive_difference(
        df,
        "planning_tiles_extra_pre",
        "PLANNING_MATT_PRE",
        "PLANNING_MATTI_MIN_PRE",
    )
    positive_difference(
        df,
        "planning_tiles_extra_post",
        "PLANNING_MATT_POST",
        "PLANNING_MATTI_MIN_POST",
    )
    positive_difference(
        df,
        "pwm_tiles_extra_pre",
        "PWM_MATT_PRE",
        "PWM_MATT_MIN_PRE",
    )
    positive_difference(
        df,
        "pwm_tiles_extra_post",
        "PWM_MATT_POST",
        "PWM_MATT_MIN_POST",
    )

    add_planning_composite(
        df,
        "PLANNING_COMPOSITE_PRE",
        "PLANNING_ACC_PRE",
        "planning_tiles_extra_pre",
    )
    add_planning_composite(
        df,
        "PLANNING_COMPOSITE_POST",
        "PLANNING_ACC_POST",
        "planning_tiles_extra_post",
    )
    add_planning_composite(
        df,
        "PWM_COMPOSITE_PRE",
        "PWM_ACC_PRE",
        "pwm_tiles_extra_pre",
    )
    add_planning_composite(
        df,
        "PWM_COMPOSITE_POST",
        "PWM_ACC_POST",
        "pwm_tiles_extra_post",
    )

    for col in LOG_VARIABLES:
        if col in df.columns:
            numeric = to_numeric(df[col])
            df[f"{col}_ln"] = numeric.where(numeric > 0).apply(np.log)

    return df


def main() -> None:
    df = build_composite_dataframe()
    print(f"Official database loaded from: {DB_PATH}")
    print("Composite variables generated in memory; no derived database workbook was written.")
    print(f"Rows: {len(df)}; columns: {len(df.columns)}")


if __name__ == "__main__":
    main()
