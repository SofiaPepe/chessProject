from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from common import build_analysis_dataset, fdr_bh, find_prepost_pairs, to_numeric, write_workbook
from config import ALPHA, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "08_sensitivity"
OUT_PATH = OUT_DIR / "pre_questionnaire_models_with_raven_covariate.xlsx"
MIN_N = 25


def zscore(series: pd.Series) -> pd.Series:
    values = to_numeric(series)
    sd = values.std(ddof=1)
    return (values - values.mean()) / sd if pd.notna(sd) and sd > 0 else pd.Series(np.nan, index=series.index)


def questionnaire_predictors(df: pd.DataFrame) -> list[str]:
    predictors = []
    for column in sorted(
        column for column in df.columns if str(column).startswith(("ABAS_", "BRIEF_"))
    ):
        values = to_numeric(df[column])
        if values.notna().sum() >= MIN_N and values.nunique(dropna=True) >= 2:
            predictors.append(column)
    return predictors


def run(df: pd.DataFrame | None = None) -> pd.DataFrame:
    if df is None:
        df = build_analysis_dataset()
    rows = []
    predictors = questionnaire_predictors(df)
    pairs = find_prepost_pairs(df)
    for predictor in predictors:
        for pair in pairs:
            base = {
                "predictor": predictor,
                "outcome": pair["variable"],
                "pre_col": pair["pre_col"],
                "domain": pair["domain"],
                "transformation": pair["transformation"],
                "n": np.nan,
                "model": "PRE outcome_z ~ questionnaire predictor_z + age_z + Raven_ACC_PRE_z",
            }
            if pair["pre_col"] == "Raven_ACC_PRE":
                rows.append({**base, "status": "skipped_outcome_is_raven"})
                continue
            data = df[[predictor, pair["pre_col"], "age", "Raven_ACC_PRE"]].copy()
            data["predictor_z"] = zscore(data[predictor])
            data["outcome_z"] = zscore(data[pair["pre_col"]])
            data["age_z"] = zscore(data["age"])
            data["raven_pre_z"] = zscore(data["Raven_ACC_PRE"])
            data = data.dropna(subset=["predictor_z", "outcome_z", "age_z", "raven_pre_z"])
            base = {
                "predictor": predictor,
                "outcome": pair["variable"],
                "pre_col": pair["pre_col"],
                "domain": pair["domain"],
                "transformation": pair["transformation"],
                "n": len(data),
                "model": "PRE outcome_z ~ questionnaire predictor_z + age_z + Raven_ACC_PRE_z",
            }
            if len(data) < MIN_N:
                rows.append({**base, "status": "insufficient_data"})
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = smf.ols(
                        "outcome_z ~ predictor_z + age_z + raven_pre_z",
                        data=data,
                    ).fit(cov_type="HC3")
                ci = fit.conf_int().loc["predictor_z"]
                rows.append(
                    {
                        **base,
                        "status": "ok",
                        "term": "predictor_z",
                        "beta_standardized": fit.params["predictor_z"],
                        "se_hc3": fit.bse["predictor_z"],
                        "ci_low": ci.iloc[0],
                        "ci_high": ci.iloc[1],
                        "p_value": fit.pvalues["predictor_z"],
                        "r_squared": fit.rsquared,
                        "adj_r_squared": fit.rsquared_adj,
                    }
                )
            except Exception as exc:
                rows.append({**base, "status": f"{type(exc).__name__}: {exc}"})
    result = fdr_bh(pd.DataFrame(rows), "p_value")
    if not result.empty:
        result["significant_p05"] = result["p_value"] < ALPHA
        result["significant_fdr05"] = result["q_fdr_bh"] < ALPHA

    original = pd.read_excel(
        OUTPUT_ROOT / "06_predictors" / "predictor_models.xlsx",
        sheet_name="pre_questionnaire_models",
    )
    original_sig = original.loc[original.get("significant_fdr05", False) == True].copy()
    raven_sig = result.loc[result.get("significant_fdr05", False) == True].copy()
    raven_ok = result.loc[result["status"].eq("ok")].copy()
    comparison = original_sig.merge(
        raven_ok,
        on=["predictor", "outcome"],
        how="left",
        suffixes=("_age_only", "_age_raven"),
        indicator=True,
    )

    summary = pd.DataFrame(
        [
            {"item": "valid_models", "value": int((result["status"] == "ok").sum())},
            {"item": "nominal_p05", "value": int(result.get("significant_p05", pd.Series(dtype=bool)).fillna(False).sum())},
            {"item": "fdr_p05", "value": int(result.get("significant_fdr05", pd.Series(dtype=bool)).fillna(False).sum())},
            {"item": "skipped_raven_outcome", "value": int((result["status"] == "skipped_outcome_is_raven").sum())},
        ]
    )
    write_workbook(
        OUT_PATH,
        {
            "summary": summary,
            "with_raven_covariate": result,
            "significant_with_raven": raven_sig,
            "compare_to_age_only_fdr": comparison,
        },
    )
    return result


def main() -> None:
    result = run()
    valid = result.loc[result["status"].eq("ok")]
    print(f"Valid models: {len(valid)}")
    print(f"Nominal p < .05: {int(valid['significant_p05'].fillna(False).sum())}")
    print(f"FDR p < .05: {int(valid['significant_fdr05'].fillna(False).sum())}")
    print(f"Workbook: {OUT_PATH}")


if __name__ == "__main__":
    main()
