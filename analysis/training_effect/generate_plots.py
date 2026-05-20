from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent / "shared"))

from training_effect_common import (  # noqa: E402
    ALPHA,
    PLOTS_DIR,
    TRAINING_OUTPUT,
    create_long_format,
    find_prepost_pairs,
    format_p,
    load_analysis_dataset,
    plot_prepost_by_group,
    safe_filename,
    standardize_metadata,
    write_excel_with_highlights,
)


RANOVA_XLSX = TRAINING_OUTPUT / "ranova" / "ranova_and_posthoc.xlsx"
COVARIATE_XLSX = TRAINING_OUTPUT / "covariate_model" / "covariate_model_results.xlsx"
PLANNING_XLSX = TRAINING_OUTPUT / "planning_minefield" / "planning_minefield_training_effect_results.xlsx"
PLANNING_SCRIPT = Path(__file__).resolve().parent / "planning_minefield" / "training_effect.py"

ALL_DIR = PLOTS_DIR / "all_variables"
SIGNIFICANT_DIR = PLOTS_DIR / "significant_interactions"
MANIFEST_XLSX = PLOTS_DIR / "plot_manifest.xlsx"


def read_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def clean_p(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def display_variable(value):
    text = str(value)
    if text.lower() == "planning_diff":
        return "Planning"
    if text.lower() == "pwm_diff":
        return "PWM"
    return value


def collect_records() -> pd.DataFrame:
    records = []

    for source, path in [
        ("RANOVA group_x_time", RANOVA_XLSX),
        ("covariate model group_x_time", COVARIATE_XLSX),
    ]:
        table = read_sheet(path, "group_x_time")
        for _, row in table.iterrows():
            p_value = clean_p(row.get("p_value"))
            records.append(
                {
                    "variable": display_variable(row.get("variable")),
                    "pre_col": row.get("pre_col"),
                    "post_col": row.get("post_col"),
                    "p_value": p_value,
                    "criterion_source": source,
                    "criterion_type": "group_x_time",
                    "p_label": "group x time",
                    "significant_p05": bool(pd.notna(p_value) and p_value < ALPHA),
                }
            )

    planning_group = read_sheet(PLANNING_XLSX, "prepost_with_group")
    if not planning_group.empty and {"effect", "p_value", "variable"}.issubset(planning_group.columns):
        model_rows = planning_group[planning_group["effect"].eq("group_x_time")]
        for _, row in model_rows.iterrows():
            p_value = clean_p(row.get("p_value"))
            records.append(
                {
                    "variable": display_variable(row.get("variable")),
                    "pre_col": row.get("pre_col"),
                    "post_col": row.get("post_col"),
                    "p_value": p_value,
                    "criterion_source": "Planning Minefield group_x_time",
                    "criterion_type": "group_x_time",
                    "p_label": "group x time",
                    "significant_p05": bool(pd.notna(p_value) and p_value < ALPHA),
                }
            )

    for sheet_name in ["t_test_pre_post", "t_test_pre_post_all"]:
        planning_ttest = read_sheet(PLANNING_XLSX, sheet_name)
        if planning_ttest.empty or "paired_t_p" not in planning_ttest.columns:
            continue
        for _, row in planning_ttest.iterrows():
            p_value = clean_p(row.get("paired_t_p"))
            records.append(
                {
                    "variable": display_variable(row.get("variable")),
                    "pre_col": row.get("pre_col"),
                    "post_col": row.get("post_col"),
                    "p_value": p_value,
                    "criterion_source": f"Planning Minefield {sheet_name}",
                    "criterion_type": "pre_post_or_group_sheet",
                    "p_label": "pre-post",
                    "group": row.get("group"),
                    "significant_p05": bool(pd.notna(p_value) and p_value < ALPHA),
                }
            )

    return pd.DataFrame(records)


def pair_key(variable) -> str:
    return str(variable).strip().upper()


def load_plot_sources() -> tuple[list[dict], dict[str, pd.DataFrame]]:
    composite = load_analysis_dataset()
    pairs = find_prepost_pairs(composite)
    data_by_variable = {pair_key(pair["variable"]): composite for pair in pairs}

    if PLANNING_SCRIPT.exists():
        spec = importlib.util.spec_from_file_location("planning_minefield_training_effect", PLANNING_SCRIPT)
        planning_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(planning_module)
        planning_df = load_analysis_dataset()
        planning_module.add_outcomes(planning_df)
        planning_df = standardize_metadata(planning_df)
        for pair in [
            {"variable": "Planning", "pre_col": "planning_diff_pre", "post_col": "planning_diff_post"},
            {"variable": "PWM", "pre_col": "pwm_diff_pre", "post_col": "pwm_diff_post"},
        ]:
            if pair["pre_col"] in planning_df.columns and pair["post_col"] in planning_df.columns:
                pairs.append(pair)
                data_by_variable[pair_key(pair["variable"])] = planning_df

    return pairs, data_by_variable


def best_record(records: pd.DataFrame, variable: str, group_time_only: bool = False) -> pd.Series | None:
    if records.empty:
        return None
    subset = records[records["variable"].astype(str).str.upper() == pair_key(variable)].copy()
    if group_time_only:
        subset = subset[subset["criterion_type"].eq("group_x_time")]
    subset = subset[subset["p_value"].notna()]
    if subset.empty:
        return None
    return subset.sort_values("p_value").iloc[0]


def source_summary(records: pd.DataFrame, variable: str) -> str:
    subset = records[
        (records["variable"].astype(str).str.upper() == pair_key(variable))
        & (records["significant_p05"].fillna(False))
    ]
    if subset.empty:
        return ""
    parts = []
    for _, row in subset.sort_values("p_value").iterrows():
        parts.append(f"{row['criterion_source']} ({format_p(row['p_value'])})")
    return "; ".join(parts)


def make_all_variable_plots(pairs: list[dict], data_by_variable: dict[str, pd.DataFrame], records: pd.DataFrame) -> pd.DataFrame:
    ALL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    seen = set()
    for pair in pairs:
        key = pair_key(pair["variable"])
        if key in seen:
            continue
        seen.add(key)
        df = data_by_variable[key]
        record = best_record(records, pair["variable"], group_time_only=True)
        p_value = None if record is None else record["p_value"]
        p_label = "group x time" if record is None else record.get("p_label", "group x time")
        path = ALL_DIR / f"{safe_filename(pair['variable'])}_prepost_by_group.png"
        try:
            long_df = create_long_format(df, pair, paired_only=False)
            plot_prepost_by_group(
                long_df,
                pair["variable"],
                path,
                p_value=p_value,
                p_label=p_label,
                title=f"{pair['variable']}: PRE vs POST by group",
            )
            manifest.append({**pair, "plot_path": str(path), "status": "created"})
        except Exception as exc:
            manifest.append({**pair, "plot_path": "", "status": f"error: {type(exc).__name__}: {exc}"})
    return pd.DataFrame(manifest)


def make_significant_plots(
    pairs: list[dict],
    data_by_variable: dict[str, pd.DataFrame],
    records: pd.DataFrame,
) -> pd.DataFrame:
    SIGNIFICANT_DIR.mkdir(parents=True, exist_ok=True)
    pair_by_key = {pair_key(pair["variable"]): pair for pair in pairs}
    significant = records[records["significant_p05"].fillna(False)].copy()
    manifest = []

    for key in sorted(significant["variable"].dropna().astype(str).str.upper().unique()):
        pair = pair_by_key.get(key)
        if not pair:
            manifest.append(
                {
                    "variable": key,
                    "plot_path": "",
                    "status": "missing_prepost_pair_for_significant_result",
                    "significant_sources": source_summary(records, key),
                }
            )
            continue

        df = data_by_variable[key]
        record = best_record(records, pair["variable"], group_time_only=False)
        path = SIGNIFICANT_DIR / f"{safe_filename(pair['variable'])}_prepost_by_group.png"
        try:
            long_df = create_long_format(df, pair, paired_only=False)
            plot_prepost_by_group(
                long_df,
                pair["variable"],
                path,
                p_value=None if record is None else record["p_value"],
                p_label="p" if record is None else record.get("p_label", "p"),
                title=f"{pair['variable']}: PRE vs POST by group",
            )
            manifest.append(
                {
                    **pair,
                    "plot_path": str(path),
                    "status": "created",
                    "best_p_value": None if record is None else record["p_value"],
                    "best_source": None if record is None else record["criterion_source"],
                    "significant_sources": source_summary(records, pair["variable"]),
                }
            )
        except Exception as exc:
            manifest.append(
                {
                    **pair,
                    "plot_path": "",
                    "status": f"error: {type(exc).__name__}: {exc}",
                    "significant_sources": source_summary(records, pair["variable"]),
                }
            )

    return pd.DataFrame(manifest)


def main() -> None:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    pairs, data_by_variable = load_plot_sources()
    records = collect_records()
    all_manifest = make_all_variable_plots(pairs, data_by_variable, records)
    significant_manifest = make_significant_plots(pairs, data_by_variable, records)

    write_excel_with_highlights(
        MANIFEST_XLSX,
        {
            "all_plots": all_manifest,
            "significant_plots": significant_manifest,
            "significance_sources": records,
        },
    )

    print("Training-effect plots complete")
    print(f"All-variable plots: {ALL_DIR}")
    print(f"Significant-result plots: {SIGNIFICANT_DIR}")
    print(f"Manifest: {MANIFEST_XLSX}")


if __name__ == "__main__":
    main()
