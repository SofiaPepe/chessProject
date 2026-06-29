from __future__ import annotations

import pandas as pd

from common import build_analysis_dataset, find_prepost_pairs
from config import INPUT_DATABASE, INPUT_SHEET, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "00_data"


def run() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = build_analysis_dataset()
    pairs = pd.DataFrame(find_prepost_pairs(df))
    xlsx = OUT_DIR / "analysis_dataset.xlsx"
    csv_path = OUT_DIR / "analysis_dataset.csv"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="analysis_dataset", index=False)
        pairs.to_excel(writer, sheet_name="prepost_dictionary", index=False)
        pd.DataFrame(
            [
                {"item": "input", "value": str(INPUT_DATABASE)},
                {"item": "input_sheet", "value": INPUT_SHEET},
                {"item": "rows", "value": len(df)},
                {"item": "columns", "value": len(df.columns)},
                {"item": "prepost_pairs", "value": len(pairs)},
                {
                    "item": "minefield_composites",
                    "value": "mean of accuracy/16*100 and recalculated route-efficiency percentage; complete components required",
                },
            ]
        ).to_excel(writer, sheet_name="manifest", index=False)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return {"data": df, "pairs": pairs, "files": [xlsx, csv_path]}
