from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = ROOT / "analysis_2"
OUTPUT_ROOT = ANALYSIS_ROOT / "output"
INPUT_DATABASE = ROOT / "data" / "FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx"
INPUT_SHEET = "Foglio1"

ID_COLUMN = "ID"
GROUP_COLUMN = "group"
GROUP_LABELS = {1: "experimental", 2: "control"}
COVARIATES = ["age"]
ALPHA = 0.05
RANDOM_SEED = 20260629

MINEFIELD_COMPOSITES = {
    "PLANNING_COMPOSITE": {
        "accuracy": "PLANNING_ACC",
        "efficiency": "PLANNING_PERC",
    },
    "PWM_COMPOSITE": {
        "accuracy": "PWM_ACC",
        "efficiency": "PWM_PERC",
    },
}

LOG_BASES = [
    "TOL_TP",
    "TOL_TE",
    "TOL_TR",
    "RAVEN_T",
    "PLANNING_TP",
    "PLANNING_TE",
    "PLANNING_TR",
    "PWM_TP",
    "PWM_TE",
    "PWM_TR",
]

# Only variables with confirmed bounds are used for normalized effectiveness.
EFFECTIVENESS_SPECS = [
    ("CBT_F_SPAN", 0, 9),
    ("CBT_B_SPAN", 0, 9),
    ("TOL_ACC", 0, 36),
    ("Raven_ACC", 0, 36),
    ("WM_ACC", 0, 8),
    ("PLANNING_ACC", 0, 16),
    ("PWM_ACC", 0, 16),
    ("PLANNING_PERC", 0, 100),
    ("PWM_PERC", 0, 100),
    ("PLANNING_COMPOSITE", 0, 100),
    ("PWM_COMPOSITE", 0, 100),
]

PCA_DOMAINS = {
    "wm": [
        "WM_SPAN",
        "WM_TRIAL",
        "WM_ACC",
    ],
    "planning": [
        "PLANNING_SPAN",
        "PLANNING_TRIAL",
        "PLANNING_ACC",
        "PLANNING_PERC",
        "PLANNING_TP",
        "PLANNING_TE",
        "PLANNING_TR",
    ],
    "wmplanning": [
        "PWM_TRIAL",
        "PWM_ACC",
        "PWM_PERC",
        "PWM_TP",
        "PWM_TE",
        "PWM_TR",
    ],
}
