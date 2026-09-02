if (!exists("SCRIPT_ROOT", inherits = FALSE)) {
  stop("SCRIPT_ROOT must be defined before sourcing config.R", call. = FALSE)
}

SCRIPT_ROOT <- normalizePath(SCRIPT_ROOT, winslash = "/", mustWork = TRUE)
SUBPROJECT_ROOT <- normalizePath(file.path(SCRIPT_ROOT, ".."), winslash = "/", mustWork = TRUE)
PROJECT_ROOT <- normalizePath(file.path(SUBPROJECT_ROOT, ".."), winslash = "/", mustWork = TRUE)

INPUT_DATABASE <- file.path(PROJECT_ROOT, "data", "FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx")
INPUT_SHEET <- "Foglio1"

OUTPUT_ROOT <- file.path(SUBPROJECT_ROOT, "output")
TABLE_ROOT <- file.path(OUTPUT_ROOT, "tables")
FIGURE_ROOT <- file.path(SUBPROJECT_ROOT, "figures")
PAPER_ROOT <- file.path(SUBPROJECT_ROOT, "paper")
REFERENCE_ROOT <- file.path(SUBPROJECT_ROOT, "references")

ALPHA <- 0.05
MIN_N <- 25L
RANDOM_SEED <- 20260901L
RAVEN_CUTOFFS <- c(`5` = 10, `6` = 11, `7` = 12)

DEMOGRAPHIC_COLUMNS <- c("ID", "age", "sex")

ABAS_STANDARD_SCALES <- c(
  "ABAS_comm_use",
  "ABAS_fun_acc",
  "ABAS_school_liv",
  "ABAS_Health_saf_sic",
  "ABAS_Leisure",
  "ABAS_Selfcare",
  "ABAS_Selfdirection",
  "ABAS_soc"
)

BRIEF_STANDARD_SCALES <- c(
  "BRIEF_Inhibit",
  "BRIEF_SelfMonitor",
  "BRIEF_shift",
  "BRIEF_Em_Con",
  "BRIEF_Initiate",
  "BRIEF_wm",
  "BRIEF_plann",
  "BRIEF_TaskMonitor",
  "BRIEF_OrganizMaterial"
)

BRIEF_INDICES <- c("BRIEF_BRI", "BRIEF_ERI", "BRIEF_CRI")

COMPLETE_TOTALS <- list(
  ABAS_TOT_complete = ABAS_STANDARD_SCALES,
  BRIEF_TOT_complete = BRIEF_STANDARD_SCALES
)

OUTCOMES <- data.frame(
  outcome = c(
    "CBT_F_SPAN", "CBT_B_SPAN", "TOL_ACC", "TOL_VIO_REG", "WM_ACC",
    "PLANNING_ACC", "PLANNING_EFF", "PWM_ACC", "PWM_EFF"
  ),
  pre_col = c(
    "CBT_F_SPAN_PRE", "CBT_B_SPAN_PRE", "TOL_ACC_PRE", "TOL_VIO_REG_PRE",
    "WM_ACC_PRE", "PLANNING_ACC_PRE", "PLANNING_EFF_PRE", "PWM_ACC_PRE",
    "PWM_EFF_PRE"
  ),
  family = c(
    "Corsi", "Corsi", "Tower of London", "Tower of London",
    "Moles working memory", "Moles planning", "Moles planning",
    "Moles working-memory planning", "Moles working-memory planning"
  ),
  stringsAsFactors = FALSE,
  check.names = FALSE
)

PREDICTOR_BLOCKS <- list(
  totals_separate = names(COMPLETE_TOTALS),
  abas_subscales = ABAS_STANDARD_SCALES,
  brief_subscales = BRIEF_STANDARD_SCALES,
  brief_indices = BRIEF_INDICES
)

EXPECTED_BLOCK_TERMS <- c(
  totals_separate = 18L,
  totals_joint = 18L,
  abas_subscales = 72L,
  brief_subscales = 81L,
  brief_indices = 27L
)

OUTCOME_LABELS <- c(
  CBT_F_SPAN = "Corsi forward span",
  CBT_B_SPAN = "Corsi backward span",
  TOL_ACC = "Tower of London accuracy",
  TOL_VIO_REG = "Tower of London rule violations",
  WM_ACC = "Moles working-memory accuracy",
  PLANNING_ACC = "Moles planning accuracy",
  PLANNING_EFF = "Moles planning tile difference (EFF)",
  PWM_ACC = "Moles WM-planning accuracy",
  PWM_EFF = "Moles WM-planning tile difference (EFF)"
)

PREDICTOR_LABELS <- c(
  ABAS_TOT_complete = "ABAS-II complete total",
  BRIEF_TOT_complete = "BRIEF-2 complete total",
  ABAS_comm_use = "ABAS Communication",
  ABAS_fun_acc = "ABAS Functional Academics",
  ABAS_school_liv = "ABAS School Living",
  ABAS_Health_saf_sic = "ABAS Health and Safety",
  ABAS_Leisure = "ABAS Leisure",
  ABAS_Selfcare = "ABAS Self-Care",
  ABAS_Selfdirection = "ABAS Self-Direction",
  ABAS_soc = "ABAS Social",
  BRIEF_Inhibit = "BRIEF Inhibit",
  BRIEF_SelfMonitor = "BRIEF Self-Monitor",
  BRIEF_shift = "BRIEF Shift",
  BRIEF_Em_Con = "BRIEF Emotional Control",
  BRIEF_Initiate = "BRIEF Initiate",
  BRIEF_wm = "BRIEF Working Memory",
  BRIEF_plann = "BRIEF Plan/Organize",
  BRIEF_TaskMonitor = "BRIEF Task-Monitor",
  BRIEF_OrganizMaterial = "BRIEF Organization of Materials",
  BRIEF_BRI = "BRIEF Behavioral Regulation Index",
  BRIEF_ERI = "BRIEF Emotional Regulation Index",
  BRIEF_CRI = "BRIEF Cognitive Regulation Index"
)
