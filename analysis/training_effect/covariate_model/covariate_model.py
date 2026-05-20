from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd
import pingouin as pg
import statsmodels.formula.api as smf

sys.path.append(str(Path(__file__).resolve().parents[1] / "shared"))

from training_effect_common import (  # noqa: E402
    ALPHA,
    COVARIATES,
    ID_COL,
    TRAINING_OUTPUT,
    add_fdr,
    create_long_format,
    find_prepost_pairs,
    load_analysis_dataset,
    to_numeric,
    write_excel_with_highlights,
)


OUT_DIR = TRAINING_OUTPUT / "covariate_model"
OUT_PATH = OUT_DIR / "covariate_model_results.xlsx"
FORMULA = "value ~ time_post * group_experimental + age + C(sex) + C(class_cov)"
INTERACTION_TERM = "time_post:group_experimental"


def prepare_model_data(long_df: pd.DataFrame) -> pd.DataFrame:
    model_df = long_df.copy()
    model_df["age"] = to_numeric(model_df["age"])
    model_df["sex"] = model_df["sex"].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
    model_df["class_cov"] = (
        model_df["class_cov"].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
    )
    return model_df.dropna(
        subset=[
            ID_COL,
            "value",
            "time_post",
            "group_experimental",
            "age",
            "sex",
            "class_cov",
        ]
    )


def fit_mixed_then_clustered_ols(model_df: pd.DataFrame):
    last_error = None
    for method in ["lbfgs", "powell", "cg", "bfgs", "nm"]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = smf.mixedlm(FORMULA, data=model_df, groups=model_df[ID_COL])
                fit = model.fit(reml=False, method=method, maxiter=2000, disp=False)
            if not getattr(fit, "converged", True):
                raise RuntimeError(f"MixedLM did not converge with {method}")
            return fit, "mixedlm_random_intercept", method
        except Exception as exc:
            last_error = exc

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.ols(FORMULA, data=model_df).fit(
            cov_type="cluster",
            cov_kwds={"groups": model_df[ID_COL]},
        )
    return fit, f"ols_clustered_by_ID_fallback_after_{type(last_error).__name__}", "clustered_ols"


def fixed_effect_table(fit, model_type: str, method: str, pair: dict[str, str], model_df: pd.DataFrame) -> pd.DataFrame:
    if model_type.startswith("mixedlm"):
        params = fit.fe_params
        bse = fit.bse.reindex(params.index)
        pvalues = fit.pvalues.reindex(params.index)
        conf = fit.conf_int().reindex(params.index)
    else:
        params = fit.params
        bse = fit.bse.reindex(params.index)
        pvalues = fit.pvalues.reindex(params.index)
        conf = fit.conf_int().reindex(params.index)

    rows = []
    for term in params.index:
        se = bse.loc[term]
        rows.append(
            {
                **pair,
                "model_type": model_type,
                "fit_method": method,
                "formula": FORMULA,
                "term": term,
                "effect": "group_x_time" if term == INTERACTION_TERM else term,
                "estimate": params.loc[term],
                "se": se,
                "z_or_t": params.loc[term] / se if pd.notna(se) and se != 0 else np.nan,
                "p_value": pvalues.loc[term],
                "ci_low": conf.loc[term, 0],
                "ci_high": conf.loc[term, 1],
                "n_obs": int(model_df.shape[0]),
                "n_ids": int(model_df[ID_COL].nunique()),
            }
        )
    return pd.DataFrame(rows)


def run_covariate_models() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_analysis_dataset()
    pairs = find_prepost_pairs(df)

    required = ["age", "sex", "class", "class_cov"]
    missing_required = [col for col in required if col not in df.columns]
    if missing_required:
        raise KeyError(f"Missing covariate column(s): {', '.join(missing_required)}")

    result_tables = []
    interaction_rows = []
    posthoc_tables = []
    skipped_rows = []

    for pair in pairs:
        try:
            long_df = create_long_format(df, pair, extra_cols=["age", "sex", "class", "class_cov"], paired_only=True)
            model_df = prepare_model_data(long_df)
            if model_df.empty or model_df["group_experimental"].nunique() < 2 or model_df[ID_COL].nunique() < 5:
                skipped_rows.append(
                    {
                        **pair,
                        "reason": "insufficient_complete_pairs_groups_or_covariates",
                        "n_obs": int(model_df.shape[0]),
                        "n_ids": int(model_df[ID_COL].nunique()) if not model_df.empty else 0,
                    }
                )
                continue

            fit, model_type, method = fit_mixed_then_clustered_ols(model_df)
            table = fixed_effect_table(fit, model_type, method, pair, model_df)
            result_tables.append(table)

            interaction = table[table["term"] == INTERACTION_TERM]
            if interaction.empty:
                p_value = np.nan
                estimate = np.nan
                model_type_used = model_type
            else:
                row = interaction.iloc[0]
                p_value = row["p_value"]
                estimate = row["estimate"]
                model_type_used = row["model_type"]

            interaction_rows.append(
                {
                    **pair,
                    "effect": "group_x_time",
                    "term": INTERACTION_TERM,
                    "estimate": estimate,
                    "p_value": p_value,
                    "significant_p05": bool(pd.notna(p_value) and p_value < ALPHA),
                    "model_type": model_type_used,
                    "n_obs": int(model_df.shape[0]),
                    "n_ids": int(model_df[ID_COL].nunique()),
                    "covariates": " + ".join(COVARIATES),
                }
            )

            if pd.notna(p_value) and p_value < ALPHA:
                posthoc = pg.pairwise_tests(
                    dv="value",
                    within="time",
                    between="group",
                    subject=ID_COL,
                    data=model_df,
                    padjust="holm",
                )
                posthoc.insert(0, "variable", pair["variable"])
                posthoc.insert(1, "pre_col", pair["pre_col"])
                posthoc.insert(2, "post_col", pair["post_col"])
                posthoc["note"] = "Unadjusted post-hoc, reported after adjusted model interaction p < .05"
                posthoc_tables.append(posthoc)
        except Exception as exc:
            skipped_rows.append({**pair, "reason": f"{type(exc).__name__}: {exc}"})

    results_df = pd.concat(result_tables, ignore_index=True) if result_tables else pd.DataFrame()
    interaction_df = pd.DataFrame(interaction_rows)
    if not interaction_df.empty:
        interaction_df = add_fdr(interaction_df, "p_value")
        interaction_df["significant_fdr05"] = interaction_df["q_fdr_bh"] < ALPHA
        interaction_df = interaction_df.sort_values(["significant_p05", "p_value"], ascending=[False, True])
    posthoc_df = pd.concat(posthoc_tables, ignore_index=True) if posthoc_tables else pd.DataFrame()
    skipped_df = pd.DataFrame(skipped_rows)
    return results_df, interaction_df, posthoc_df, skipped_df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_df, interaction_df, posthoc_df, skipped_df = run_covariate_models()
    write_excel_with_highlights(
        OUT_PATH,
        {
            "model_results": results_df,
            "group_x_time": interaction_df,
            "POST_HOC": posthoc_df,
            "skipped": skipped_df,
        },
    )
    print("Covariate training-effect models complete")
    print(f"Results workbook: {OUT_PATH}")
    print(f"Variables tested: {len(interaction_df)}")
    if not interaction_df.empty:
        print(f"p < .05 group x time interactions: {int(interaction_df['significant_p05'].sum())}")


if __name__ == "__main__":
    main()
