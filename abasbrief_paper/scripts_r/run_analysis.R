script_argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_argument) != 1L) {
  stop("Unable to determine run_analysis.R location", call. = FALSE)
}
SCRIPT_ROOT <- dirname(normalizePath(sub("^--file=", "", script_argument), winslash = "/"))
source(file.path(SCRIPT_ROOT, "config.R"), local = FALSE, encoding = "UTF-8")
source(file.path(SCRIPT_ROOT, "analysis_core.R"), local = FALSE, encoding = "UTF-8")

result <- run_analysis()
cat("ABAS-II/BRIEF-2 PRE-only analysis complete in R\n")
cat("Primary sample:", nrow(result$analysis), "\n")
cat("Model terms:", sum(result$models$status == "ok"), "\n")
cat("FDR-significant terms:", sum(result$models$significant_fdr05, na.rm = TRUE), "\n")
cat("Workbook:", file.path(OUTPUT_ROOT, "analysis_results.xlsx"), "\n")
