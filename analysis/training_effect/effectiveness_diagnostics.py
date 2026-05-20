from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "analysis" / "descriptives"))
sys.path.append(str(ROOT / "analysis" / "training_effect"))

from add_composites import build_composite_dataframe, to_numeric  # noqa: E402
from treatment_effectiveness import (  # noqa: E402
    GROUP_LABELS,
    build_individual_effectiveness,
    hedges_g,
    load_metadata,
)


OUT_DIR = ROOT / "output" / "training_effect" / "treatment_effectiveness"
OUT_PATH = OUT_DIR / "effectiveness_diagnostics.xlsx"
COMPOSITE_METADATA_PATH = ROOT / "analysis" / "shared" / "composite_metadata.csv"


def compare_groups(data: pd.DataFrame, label: str) -> pd.DataFrame:
    rows = []
    for variable, subset in data.groupby("variable"):
        exp = subset.loc[subset["group"] == 1, "effectiveness_pct"].dropna()
        ctrl = subset.loc[subset["group"] == 2, "effectiveness_pct"].dropna()
        if exp.empty or ctrl.empty:
            rows.append({"analysis": label, "variable": variable, "status": "skipped_missing_group"})
            continue

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            t_stat, t_p = stats.ttest_ind(exp, ctrl, equal_var=False, nan_policy="omit")

        try:
            mw_p = stats.mannwhitneyu(exp, ctrl, alternative="two-sided").pvalue
        except ValueError:
            mw_p = np.nan

        rows.append(
            {
                "analysis": label,
                "variable": variable,
                "status": "ok",
                "experimental_n": int(exp.count()),
                "control_n": int(ctrl.count()),
                "experimental_mean": exp.mean(),
                "control_mean": ctrl.mean(),
                "mean_difference_exp_minus_control": exp.mean() - ctrl.mean(),
                "hedges_g": hedges_g(exp, ctrl),
                "welch_t": t_stat,
                "welch_p": t_p,
                "mann_whitney_p": mw_p,
            }
        )
    return pd.DataFrame(rows)


def boundary_counts(individual: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variable, group_label), subset in individual.groupby(["variable", "group_label"]):
        min_possible = subset["min_possible"].dropna().iloc[0] if subset["min_possible"].notna().any() else np.nan
        max_possible = subset["max_possible"].dropna().iloc[0] if subset["max_possible"].notna().any() else np.nan
        for time_label, value_col in [("pre", "pre_value"), ("post", "post_value")]:
            values = to_numeric(subset[value_col])
            row = {
                "variable": variable,
                "group": group_label,
                "time": time_label,
                "n": int(values.notna().sum()),
                "missing": int(values.isna().sum()),
                "zero_count": int((values == 0).sum()),
                "zero_pct": (values == 0).mean() * 100,
            }
            if pd.notna(min_possible):
                row["at_min_count"] = int((values == min_possible).sum())
            if pd.notna(max_possible):
                row["at_max_count"] = int((values == max_possible).sum())
            rows.append(row)
    return pd.DataFrame(rows)


def status_counts(individual: pd.DataFrame) -> pd.DataFrame:
    return (
        individual.groupby(["variable", "group_label", "effectiveness_status"], dropna=False)
        .size()
        .reset_index(name="n")
    )


def outlier_rows(individual: pd.DataFrame) -> pd.DataFrame:
    ok = individual[individual["effectiveness_status"].eq("ok")].copy()
    ok["absolute_effectiveness"] = ok["effectiveness_pct"].abs()
    return ok[
        (ok["effectiveness_pct"] < -100)
        | (ok["effectiveness_pct"] > 100)
        | (ok["absolute_effectiveness"] >= 200)
    ].sort_values(["variable", "absolute_effectiveness"], ascending=[True, False])


def sensitivity_sets(individual: pd.DataFrame) -> pd.DataFrame:
    ok = individual[individual["effectiveness_status"].eq("ok")].copy()
    rows = [compare_groups(ok, "primary_ok_values")]

    no_extreme = ok[ok["effectiveness_pct"].between(-100, 100)].copy()
    rows.append(compare_groups(no_extreme, "exclude_effectiveness_outside_minus100_plus100"))

    no_zero_cbt_f_post = ok[
        ~(
            ok["variable"].eq("CBT_F_SPAN")
            & to_numeric(ok["post_value"]).eq(0)
        )
    ].copy()
    rows.append(compare_groups(no_zero_cbt_f_post, "exclude_CBT_F_SPAN_POST_zero"))

    return pd.concat(rows, ignore_index=True)


def write_workbook(
    metadata: pd.DataFrame,
    individual: pd.DataFrame,
    boundaries: pd.DataFrame,
    statuses: pd.DataFrame,
    outliers: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readme = pd.DataFrame(
        [
            {"item": "input_database", "value": "data/FINAL_DATABASE.xlsx"},
            {"item": "purpose", "value": "Diagnostics for treatment-effectiveness results"},
            {
                "item": "primary_analysis_unchanged",
                "value": "This workbook does not recode or remove values from the primary analysis.",
            },
            {
                "item": "sensitivity_exclude_extreme_effectiveness",
                "value": "Excludes effectiveness_pct outside [-100, 100].",
            },
            {
                "item": "sensitivity_exclude_CBT_F_SPAN_POST_zero",
                "value": "Explores impact of treating CBT_F_SPAN post-test zeros as potentially problematic.",
            },
        ]
    )
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        readme.to_excel(writer, sheet_name="readme", index=False)
        metadata.to_excel(writer, sheet_name="variable_metadata", index=False)
        if COMPOSITE_METADATA_PATH.exists():
            pd.read_csv(COMPOSITE_METADATA_PATH).to_excel(writer, sheet_name="composite_metadata", index=False)
        boundaries.to_excel(writer, sheet_name="zero_boundary_counts", index=False)
        statuses.to_excel(writer, sheet_name="status_counts", index=False)
        outliers.to_excel(writer, sheet_name="extreme_effectiveness", index=False)
        sensitivity.to_excel(writer, sheet_name="sensitivity_comparisons", index=False)


def main() -> None:
    df = build_composite_dataframe()
    df["group"] = pd.to_numeric(df["group"], errors="coerce")
    metadata, _ = load_metadata(df)
    individual = build_individual_effectiveness(df, metadata)
    individual["group_label"] = individual["group"].map(GROUP_LABELS)

    boundaries = boundary_counts(individual)
    statuses = status_counts(individual)
    outliers = outlier_rows(individual)
    sensitivity = sensitivity_sets(individual)
    write_workbook(metadata, individual, boundaries, statuses, outliers, sensitivity)

    suspicious_zero = boundaries[
        boundaries["time"].eq("post")
        & boundaries["variable"].eq("CBT_F_SPAN")
        & boundaries["zero_count"].gt(0)
    ]
    print("Effectiveness diagnostics complete")
    print(f"Extreme effectiveness rows: {len(outliers)}")
    print("CBT_F_SPAN post zeros:")
    print(suspicious_zero.to_string(index=False))
    print(f"Workbook: {OUT_PATH}")


if __name__ == "__main__":
    main()
