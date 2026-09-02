script_argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_argument) != 1L) {
  stop("Unable to determine test_analysis.R location", call. = FALSE)
}
TEST_ROOT <- dirname(normalizePath(sub("^--file=", "", script_argument), winslash = "/"))
SCRIPT_ROOT <- normalizePath(file.path(TEST_ROOT, ".."), winslash = "/", mustWork = TRUE)
source(file.path(SCRIPT_ROOT, "config.R"), local = FALSE, encoding = "UTF-8")
source(file.path(SCRIPT_ROOT, "analysis_core.R"), local = FALSE, encoding = "UTF-8")

assert_true <- function(condition, message) {
  if (!isTRUE(condition)) stop(message, call. = FALSE)
}

prepared <- load_and_prepare()
assert_true(nrow(prepared$full) == 101L, "Source sample must contain 101 participants")
assert_true(sum(prepared$full$raven_flag) == 2L, "Raven screening must exclude two participants")
assert_true(nrow(prepared$analysis) == 99L, "Primary sample must contain 99 participants")

forbidden <- names(prepared$analysis)[
  grepl("_POST$", names(prepared$analysis), ignore.case = TRUE) |
    grepl("RAVEN", names(prepared$analysis), ignore.case = TRUE) |
    tolower(names(prepared$analysis)) %in% c("group", "id")
]
assert_true(length(forbidden) == 0L, "Model data must be PRE-only and deidentified")
assert_true(
  setequal(
    OUTCOMES$outcome,
    c(
      "CBT_F_SPAN", "CBT_B_SPAN", "TOL_ACC", "TOL_VIO_REG", "WM_ACC",
      "PLANNING_ACC", "PLANNING_EFF", "PWM_ACC", "PWM_EFF"
    )
  ),
  "Outcome set differs from the nine prespecified outcomes"
)

for (total in names(COMPLETE_TOTALS)) {
  observed <- prepared$full[[paste0(total, "_components_observed")]]
  assert_true(
    all(is.na(prepared$full[[total]][observed < length(COMPLETE_TOTALS[[total]])])),
    paste(total, "must be missing unless all components are observed")
  )
  assert_true(
    all(!is.na(prepared$full[[total]][observed == length(COMPLETE_TOTALS[[total]])])),
    paste(total, "must be present when all components are observed")
  )
}
assert_true(sum(!is.na(prepared$analysis$ABAS_TOT_complete)) == 95L, "ABAS total n must be 95")
assert_true(sum(!is.na(prepared$analysis$BRIEF_TOT_complete)) == 96L, "BRIEF total n must be 96")

models <- run_primary_models(prepared$analysis)
ok <- models[models$status == "ok", , drop = FALSE]
assert_true(nrow(ok) == 216L, "There must be 216 valid model terms")
assert_true(sum(ok$significant_fdr05) == 22L, "There must be 22 FDR-significant terms")
assert_true(
  !any(grepl("Raven|POST|group", ok$formula, ignore.case = TRUE)),
  "Model formulas contain a forbidden term"
)
assert_true(!any(ok$outcome %in% c("PLANNING_OST", "PWM_OST")), "OST outcomes must be excluded")

key_result <- models[
  models$block == "abas_subscales" &
    models$predictor == "ABAS_fun_acc" &
    models$outcome == "CBT_B_SPAN",
  , drop = FALSE
]
assert_true(nrow(key_result) == 1L, "Key replication result is missing")
assert_true(
  abs(key_result$beta_standardized - 0.3964463245474208) < 1e-10,
  "Key standardized coefficient does not replicate"
)
assert_true(
  abs(key_result$q_fdr_bh - 0.014316094100629586) < 1e-10,
  "Key FDR-adjusted q value does not replicate"
)

required_outputs <- c(
  file.path(OUTPUT_ROOT, "analysis_results.xlsx"),
  file.path(OUTPUT_ROOT, "analysis_summary.md"),
  file.path(TABLE_ROOT, "all_primary_models.csv"),
  file.path(TABLE_ROOT, "fdr_significant_models.csv"),
  file.path(FIGURE_ROOT, "primary_forest_plot.png"),
  file.path(FIGURE_ROOT, "primary_forest_plot.svg"),
  file.path(FIGURE_ROOT, "significant_beta_heatmap.png"),
  file.path(FIGURE_ROOT, "significant_beta_heatmap.svg")
)
assert_true(all(file.exists(required_outputs)), "One or more aggregate outputs are missing")

sheet_names <- openxlsx::getSheetNames(file.path(OUTPUT_ROOT, "analysis_results.xlsx"))
for (sheet in sheet_names) {
  frame <- openxlsx::read.xlsx(
    file.path(OUTPUT_ROOT, "analysis_results.xlsx"), sheet = sheet,
    check.names = FALSE
  )
  assert_true(!("ID" %in% names(frame)), paste("Participant ID found in sheet", sheet))
  assert_true(
    !any(grepl("_POST$", names(frame), ignore.case = TRUE)),
    paste("POST column found in sheet", sheet)
  )
}

cat("All R analysis tests passed.\n")
