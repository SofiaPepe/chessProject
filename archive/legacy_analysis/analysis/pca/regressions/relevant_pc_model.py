from pathlib import Path
import os
import sys

import pandas as pd
import pingouin as pg


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "output" / "pca"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.append(str(ROOT / "analysis" / "descriptives"))

from add_composites import build_composite_dataframe  # noqa: E402


planning_pc_path = OUTPUT_DIR / "relevant_pcs_planning.xlsx"
wm_pc_path = OUTPUT_DIR / "relevant_pcs_wm.xlsx"
wmplanning_pc_path = OUTPUT_DIR / "relevant_pcs_wmplanning.xlsx"


def main() -> None:
    df = build_composite_dataframe()
    planning_pc = pd.read_excel(planning_pc_path, index_col=0)
    wm_pc = pd.read_excel(wm_pc_path, index_col=0)
    wmplanning_pc = pd.read_excel(wmplanning_pc_path, index_col=0)

    df = df.merge(planning_pc, left_index=True, right_index=True, how="left")
    df = df.merge(wm_pc, left_index=True, right_index=True, how="left")
    df = df.merge(wmplanning_pc, left_index=True, right_index=True, how="left")

    for col in df.columns:
        if col.startswith("PC"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    results = []
    predictors = [col for col in ["group", "age", "sex"] if col in df.columns]
    for pc in [col for col in df.columns if col.startswith("PC")]:
        if df[pc].dropna().empty:
            print(f"Skipping {pc}: empty or non-numeric column")
            continue
        try:
            temp_df = df[[pc] + predictors].copy()
            temp_df[pc] = pd.to_numeric(temp_df[pc], errors="coerce")
            temp_df = temp_df.replace([float("inf"), float("-inf")], pd.NA).dropna()
            if temp_df.empty:
                print(f"Skipping {pc}: no valid data after cleaning")
                continue
            lm = pg.linear_regression(temp_df[predictors], temp_df[pc])
            lm.insert(0, "PC", pc)
            results.append(lm)
        except Exception as exc:
            print(f"Error for {pc}: {exc}")

    if results:
        out_path = OUTPUT_DIR / "relevant_pc_model.xlsx"
        pd.concat(results, ignore_index=True).to_excel(out_path, index=False)
        print(f"Linear-model results saved to {out_path}")
    else:
        print("No result available.")


if __name__ == "__main__":
    main()
