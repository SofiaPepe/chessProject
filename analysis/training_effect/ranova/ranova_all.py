from pathlib import Path
import sys

import pandas as pd
import pingouin as pg

sys.path.append(str(Path(__file__).resolve().parents[1] / "shared"))

from training_effect_common import (  # noqa: E402
    ALPHA,
    GROUP_COL,
    ID_COL,
    TRAINING_OUTPUT,
    add_fdr,
    create_long_format,
    find_prepost_pairs,
    load_analysis_dataset,
    write_excel_with_highlights,
)


OUT_DIR = TRAINING_OUTPUT / "ranova"
OUT_PATH = OUT_DIR / "ranova_and_posthoc.xlsx"


def p_column(frame: pd.DataFrame) -> str | None:
    for candidate in ["p-unc", "p_unc", "p-GG-corr", "p-GG", "p-corr", "pval", "p_value"]:
        if candidate in frame.columns:
            return candidate
    for col in frame.columns:
        col_lower = str(col).lower()
        if col_lower.startswith("p-") or col_lower.startswith("p_"):
            return col
    return None


def interaction_p(anova: pd.DataFrame) -> float | None:
    if "Source" not in anova.columns:
        return None
    p_col = p_column(anova)
    if not p_col:
        return None
    source = anova["Source"].astype(str).str.lower()
    mask = source.isin(["interaction", "group * time", "group:time", "time * group", "time:group"])
    if not mask.any():
        return None
    return anova.loc[mask, p_col].iloc[0]


def run_ranova() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_analysis_dataset()
    pairs = find_prepost_pairs(df)

    anova_results = []
    interaction_rows = []
    posthoc_results = []
    skipped_rows = []

    for pair in pairs:
        try:
            long_df = create_long_format(df, pair, paired_only=True)
            if long_df.empty or long_df[GROUP_COL].nunique() < 2 or long_df[ID_COL].nunique() < 3:
                skipped_rows.append(
                    {
                        **pair,
                        "reason": "insufficient_complete_pairs_or_groups",
                        "n_obs": int(long_df.shape[0]),
                        "n_ids": int(long_df[ID_COL].nunique()) if not long_df.empty else 0,
                    }
                )
                continue

            aov = pg.mixed_anova(
                dv="value",
                within="time",
                between=GROUP_COL,
                subject=ID_COL,
                data=long_df,
            )
            aov.insert(0, "variable", pair["variable"])
            aov.insert(1, "pre_col", pair["pre_col"])
            aov.insert(2, "post_col", pair["post_col"])
            if "Source" in aov.columns:
                aov["effect_focus"] = aov["Source"].replace({"Interaction": "group_x_time"})
            anova_results.append(aov)

            p_value = interaction_p(aov)
            interaction_rows.append(
                {
                    **pair,
                    "effect": "group_x_time",
                    "p_value": p_value,
                    "significant_p05": bool(pd.notna(p_value) and p_value < ALPHA),
                    "n_obs": int(long_df.shape[0]),
                    "n_ids": int(long_df[ID_COL].nunique()),
                }
            )

            if pd.notna(p_value) and p_value < ALPHA:
                posthoc = pg.pairwise_tests(
                    dv="value",
                    within="time",
                    between=GROUP_COL,
                    subject=ID_COL,
                    data=long_df,
                    padjust="holm",
                )
                posthoc.insert(0, "variable", pair["variable"])
                posthoc.insert(1, "pre_col", pair["pre_col"])
                posthoc.insert(2, "post_col", pair["post_col"])
                posthoc_results.append(posthoc)
        except Exception as exc:
            skipped_rows.append({**pair, "reason": f"{type(exc).__name__}: {exc}"})

    anova_df = pd.concat(anova_results, ignore_index=True) if anova_results else pd.DataFrame()
    interaction_df = pd.DataFrame(interaction_rows)
    if not interaction_df.empty:
        interaction_df = add_fdr(interaction_df, "p_value")
        interaction_df["significant_fdr05"] = interaction_df["q_fdr_bh"] < ALPHA
        interaction_df = interaction_df.sort_values(["significant_p05", "p_value"], ascending=[False, True])
    posthoc_df = pd.concat(posthoc_results, ignore_index=True) if posthoc_results else pd.DataFrame()
    skipped_df = pd.DataFrame(skipped_rows)

    return anova_df, interaction_df, posthoc_df, skipped_df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    anova_df, interaction_df, posthoc_df, skipped_df = run_ranova()
    write_excel_with_highlights(
        OUT_PATH,
        {
            "ANOVA": anova_df,
            "group_x_time": interaction_df,
            "POST_HOC": posthoc_df,
            "skipped": skipped_df,
        },
    )
    print("RANOVA training-effect analysis complete")
    print(f"Results workbook: {OUT_PATH}")
    print(f"Variables tested: {len(interaction_df)}")
    if not interaction_df.empty:
        print(f"p < .05 group x time interactions: {int(interaction_df['significant_p05'].sum())}")


if __name__ == "__main__":
    main()
