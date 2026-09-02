from __future__ import annotations

from pathlib import Path


SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SUBPROJECT_ROOT.parent
INPUT_DATABASE = PROJECT_ROOT / "data" / "FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx"
INPUT_SHEET = "Foglio1"

OUTPUT_ROOT = SUBPROJECT_ROOT / "output"
TABLE_ROOT = OUTPUT_ROOT / "tables"
FIGURE_ROOT = SUBPROJECT_ROOT / "figures"
PAPER_ROOT = SUBPROJECT_ROOT / "paper"
REFERENCE_ROOT = SUBPROJECT_ROOT / "references"

ALPHA = 0.05
MIN_N = 25
RANDOM_SEED = 20260901
RAVEN_CUTOFFS = {5: 10, 6: 11, 7: 12}

DEMOGRAPHIC_COLUMNS = ["ID", "age", "sex"]

ABAS_STANDARD_SCALES = [
    "ABAS_comm_use",
    "ABAS_fun_acc",
    "ABAS_school_liv",
    "ABAS_Health_saf_sic",
    "ABAS_Leisure",
    "ABAS_Selfcare",
    "ABAS_Selfdirection",
    "ABAS_soc",
]

BRIEF_STANDARD_SCALES = [
    "BRIEF_Inhibit",
    "BRIEF_SelfMonitor",
    "BRIEF_shift",
    "BRIEF_Em_Con",
    "BRIEF_Initiate",
    "BRIEF_wm",
    "BRIEF_plann",
    "BRIEF_TaskMonitor",
    "BRIEF_OrganizMaterial",
]

BRIEF_INDICES = ["BRIEF_BRI", "BRIEF_ERI", "BRIEF_CRI"]

COMPLETE_TOTALS = {
    "ABAS_TOT_complete": ABAS_STANDARD_SCALES,
    "BRIEF_TOT_complete": BRIEF_STANDARD_SCALES,
}

OUTCOMES = [
    ("CBT_F_SPAN", "CBT_F_SPAN_PRE", "Corsi"),
    ("CBT_B_SPAN", "CBT_B_SPAN_PRE", "Corsi"),
    ("TOL_ACC", "TOL_ACC_PRE", "Tower of London"),
    ("TOL_VIO_REG", "TOL_VIO_REG_PRE", "Tower of London"),
    ("WM_ACC", "WM_ACC_PRE", "Moles working memory"),
    ("PLANNING_ACC", "PLANNING_ACC_PRE", "Moles planning"),
    ("PLANNING_EFF", "PLANNING_EFF_PRE", "Moles planning"),
    ("PWM_ACC", "PWM_ACC_PRE", "Moles working-memory planning"),
    ("PWM_EFF", "PWM_EFF_PRE", "Moles working-memory planning"),
]

PREDICTOR_BLOCKS = {
    "totals_separate": list(COMPLETE_TOTALS),
    "abas_subscales": ABAS_STANDARD_SCALES,
    "brief_subscales": BRIEF_STANDARD_SCALES,
    "brief_indices": BRIEF_INDICES,
}

EXPECTED_BLOCK_TERMS = {
    "totals_separate": 18,
    "totals_joint": 18,
    "abas_subscales": 72,
    "brief_subscales": 81,
    "brief_indices": 27,
}

OUTCOME_LABELS = {
    "CBT_F_SPAN": "Corsi forward span",
    "CBT_B_SPAN": "Corsi backward span",
    "TOL_ACC": "Tower of London accuracy",
    "TOL_VIO_REG": "Tower of London rule violations",
    "WM_ACC": "Moles working-memory accuracy",
    "PLANNING_ACC": "Moles planning accuracy",
    "PLANNING_EFF": "Moles planning tile difference (EFF)",
    "PWM_ACC": "Moles WM-planning accuracy",
    "PWM_EFF": "Moles WM-planning tile difference (EFF)",
}

PREDICTOR_LABELS = {
    "ABAS_TOT_complete": "ABAS-II complete total",
    "BRIEF_TOT_complete": "BRIEF-2 complete total",
    "ABAS_comm_use": "ABAS Communication",
    "ABAS_fun_acc": "ABAS Functional Academics",
    "ABAS_school_liv": "ABAS School Living",
    "ABAS_Health_saf_sic": "ABAS Health and Safety",
    "ABAS_Leisure": "ABAS Leisure",
    "ABAS_Selfcare": "ABAS Self-Care",
    "ABAS_Selfdirection": "ABAS Self-Direction",
    "ABAS_soc": "ABAS Social",
    "BRIEF_Inhibit": "BRIEF Inhibit",
    "BRIEF_SelfMonitor": "BRIEF Self-Monitor",
    "BRIEF_shift": "BRIEF Shift",
    "BRIEF_Em_Con": "BRIEF Emotional Control",
    "BRIEF_Initiate": "BRIEF Initiate",
    "BRIEF_wm": "BRIEF Working Memory",
    "BRIEF_plann": "BRIEF Plan/Organize",
    "BRIEF_TaskMonitor": "BRIEF Task-Monitor",
    "BRIEF_OrganizMaterial": "BRIEF Organization of Materials",
    "BRIEF_BRI": "BRIEF Behavioral Regulation Index",
    "BRIEF_ERI": "BRIEF Emotional Regulation Index",
    "BRIEF_CRI": "BRIEF Cognitive Regulation Index",
}
