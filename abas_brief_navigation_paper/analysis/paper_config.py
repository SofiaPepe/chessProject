from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBPROJECT_ROOT = PROJECT_ROOT / "abas_brief_navigation_paper"
ANALYSIS_ROOT = SUBPROJECT_ROOT / "analysis"
OUTPUT_ROOT = SUBPROJECT_ROOT / "output"
PAPER_ROOT = SUBPROJECT_ROOT / "paper"

MIN_N = 25
ALPHA = 0.05
RANDOM_SEED = 20260701

DEMOGRAPHIC_COLUMNS = [
    "ID",
    "age",
    "sex",
    "class",
    "section",
    "hand",
    "semestre",
]

PRIMARY_MODEL_LABEL = "outcome_PRE_z ~ questionnaire_z + age_z"
RAVEN_MODEL_LABEL = "outcome_PRE_z ~ questionnaire_z + age_z + Raven_ACC_PRE_z"

