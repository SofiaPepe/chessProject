from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "shared"))

from planning_minefield_common import (
    add_mixed_predictors,
    add_outcomes,
    add_sum_outcomes,
    load_planning_dataset,
    run_predictor_models,
    run_predictor_models_mix,
    style_workbook,
)


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "output" / "predictors" / "planning_minefield"
RESULTS_XLSX = OUT_DIR / "planning_minefield_regression_results.xlsx"


def write_regression_workbook(path, predictors_pre, predictors_post, predictors_mix):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        predictors_pre.to_excel(writer, sheet_name="predictors_pre", index=False)
        predictors_post.to_excel(writer, sheet_name="predictors_post", index=False)
        predictors_mix.to_excel(writer, sheet_name="predictors_mixed_sum", index=False)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_planning_dataset()
    add_outcomes(df)
    add_sum_outcomes(df)
    mixed_predictors = add_mixed_predictors(df)

    predictors_pre = run_predictor_models(df, "PRE")
    predictors_post = run_predictor_models(df, "POST")
    predictors_mix = run_predictor_models_mix(df, mixed_predictors)

    write_regression_workbook(RESULTS_XLSX, predictors_pre, predictors_post, predictors_mix)
    style_workbook(RESULTS_XLSX)

    print("Planning Minefield regression analysis complete")
    print(f"Results workbook: {RESULTS_XLSX}")


if __name__ == "__main__":
    main()
