from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "FINAL_DATABASE.xlsx"
OUTPUT_DIR = ROOT / "output" / "descriptives"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "final_database_normalized_columns.xlsx"

SUFFIX_SPACE_PATTERN = re.compile(r"_\s+(PRE|POST)$")


def normalize_column_name(column: str) -> str:
    column = str(column).strip()
    return re.sub(SUFFIX_SPACE_PATTERN, r"_\1", column)


def main() -> None:
    df = pd.read_excel(INPUT_PATH)
    df.columns = [normalize_column_name(column) for column in df.columns]
    df.to_excel(OUTPUT_PATH, index=False)
    print(f"Normalized copy saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
