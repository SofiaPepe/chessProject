script_argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_argument) != 1L) {
  stop("Unable to determine verify_parity.R location", call. = FALSE)
}
SCRIPT_ROOT <- dirname(normalizePath(sub("^--file=", "", script_argument), winslash = "/"))
source(file.path(SCRIPT_ROOT, "config.R"), local = FALSE, encoding = "UTF-8")

assert_packages <- function(packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) > 0L) {
    stop("Missing required R packages: ", paste(missing, collapse = ", "), call. = FALSE)
  }
}
assert_packages(c("openxlsx"))

python <- Sys.which("python")
if (!nzchar(python)) stop("Python is not available on PATH", call. = FALSE)
rscript <- file.path(R.home("bin"), "Rscript.exe")
if (!file.exists(rscript)) rscript <- file.path(R.home("bin"), "Rscript")
if (!file.exists(rscript)) stop("Rscript executable not found", call. = FALSE)

run_checked <- function(executable, arguments, label) {
  status <- system2(
    executable, args = vapply(arguments, shQuote, character(1)),
    stdout = "", stderr = ""
  )
  if (!identical(status, 0L)) {
    stop(label, " failed with exit status ", status, call. = FALSE)
  }
}

read_csv_result <- function(name) {
  utils::read.csv(
    file.path(TABLE_ROOT, name), stringsAsFactors = FALSE,
    check.names = FALSE, na.strings = c(""), fileEncoding = "UTF-8-BOM"
  )
}

stable_sheets <- c(
  "participants", "screening_by_age", "variable_dictionary",
  "outcome_descriptives", "predictor_descriptives", "correlations",
  "model_results", "block_summary", "significant_results",
  "significant_diagnostics"
)

read_workbook_results <- function() {
  path <- file.path(OUTPUT_ROOT, "analysis_results.xlsx")
  stats::setNames(lapply(stable_sheets, function(sheet) {
    openxlsx::read.xlsx(path, sheet = sheet, check.names = FALSE)
  }), stable_sheets)
}

csv_names <- c(
  "all_primary_models.csv", "fdr_significant_models.csv",
  "outcome_descriptives.csv", "block_summary.csv",
  "significant_model_diagnostics.csv"
)
markdown_names <- c(
  "table1_participants.md", "table2_outcomes.md", "table3_block_summary.md",
  "table4_totals.md", "table5_subscales_indices.md", "results_narrative.md"
)

python_script <- file.path(SUBPROJECT_ROOT, "scripts", "run_analysis.py")
r_script <- file.path(SCRIPT_ROOT, "run_analysis.R")

cat("Generating the Python reference outputs...\n")
run_checked(python, python_script, "Python reference analysis")
python_csv <- stats::setNames(lapply(csv_names, read_csv_result), csv_names)
python_workbook <- read_workbook_results()
python_markdown <- stats::setNames(lapply(markdown_names, function(name) {
  paste(readLines(file.path(TABLE_ROOT, name), warn = FALSE, encoding = "UTF-8"), collapse = "\n")
}), markdown_names)

cat("Generating the R outputs...\n")
run_checked(rscript, r_script, "R analysis")
r_csv <- stats::setNames(lapply(csv_names, read_csv_result), csv_names)
r_workbook <- read_workbook_results()
r_markdown <- stats::setNames(lapply(markdown_names, function(name) {
  paste(readLines(file.path(TABLE_ROOT, name), warn = FALSE, encoding = "UTF-8"), collapse = "\n")
}), markdown_names)

comparison_rows <- list()
comparison_index <- 1L

normalise_text <- function(values) {
  result <- as.character(values)
  result[is.na(values)] <- NA_character_
  result
}

compare_frames <- function(reference, candidate, name, tolerance = 1e-8) {
  if (!identical(dim(reference), dim(candidate))) {
    stop(name, " dimensions differ: Python ", paste(dim(reference), collapse = "x"),
         ", R ", paste(dim(candidate), collapse = "x"), call. = FALSE)
  }
  if (!identical(names(reference), names(candidate))) {
    stop(name, " column names or order differ", call. = FALSE)
  }
  maximum_difference <- 0
  numeric_columns <- character()
  for (column in names(reference)) {
    reference_values <- reference[[column]]
    candidate_values <- candidate[[column]]
    numeric_pair <- is.numeric(reference_values) && is.numeric(candidate_values)
    if (numeric_pair) {
      if (!identical(is.na(reference_values), is.na(candidate_values))) {
        stop(name, " NA pattern differs in ", column, call. = FALSE)
      }
      observed <- !is.na(reference_values)
      difference <- if (any(observed)) {
        max(abs(reference_values[observed] - candidate_values[observed]))
      } else {
        0
      }
      if (!is.finite(difference)) difference <- 0
      maximum_difference <- max(maximum_difference, difference)
      numeric_columns <- c(numeric_columns, column)
      if (difference > tolerance) {
        stop(
          name, " differs in numeric column ", column,
          " (maximum absolute difference ", format(difference, scientific = TRUE), ")",
          call. = FALSE
        )
      }
    } else {
      reference_text <- normalise_text(reference_values)
      candidate_text <- normalise_text(candidate_values)
      equal <- (is.na(reference_text) & is.na(candidate_text)) |
        (!is.na(reference_text) & !is.na(candidate_text) & reference_text == candidate_text)
      if (!all(equal)) {
        first <- which(!equal)[1]
        stop(
          name, " differs in text column ", column, " at row ", first,
          ": Python=", reference_text[first], ", R=", candidate_text[first],
          call. = FALSE
        )
      }
    }
  }
  comparison_rows[[comparison_index]] <<- data.frame(
    comparison = name,
    rows = nrow(reference),
    columns = ncol(reference),
    numeric_columns = length(numeric_columns),
    maximum_absolute_difference = maximum_difference,
    status = "PASS",
    stringsAsFactors = FALSE
  )
  comparison_index <<- comparison_index + 1L
}

for (name in csv_names) {
  compare_frames(python_csv[[name]], r_csv[[name]], paste0("CSV: ", name))
}
for (sheet in stable_sheets) {
  compare_frames(
    python_workbook[[sheet]], r_workbook[[sheet]], paste0("Workbook: ", sheet)
  )
}
for (name in markdown_names) {
  if (!identical(python_markdown[[name]], r_markdown[[name]])) {
    stop("Paper table differs: ", name, call. = FALSE)
  }
  comparison_rows[[comparison_index]] <- data.frame(
    comparison = paste0("Markdown: ", name),
    rows = length(readLines(file.path(TABLE_ROOT, name), warn = FALSE, encoding = "UTF-8")),
    columns = NA_integer_,
    numeric_columns = NA_integer_,
    maximum_absolute_difference = 0,
    status = "PASS",
    stringsAsFactors = FALSE
  )
  comparison_index <- comparison_index + 1L
}

report <- do.call(rbind, comparison_rows)
report_path <- file.path(OUTPUT_ROOT, "r_python_parity_report.csv")
utils::write.csv(report, report_path, row.names = FALSE, na = "")
cat("Python/R parity verification passed.\n")
cat("Compared CSV files:", length(csv_names), "\n")
cat("Compared workbook sheets:", length(stable_sheets), "\n")
cat("Compared paper Markdown files:", length(markdown_names), "\n")
cat("Report:", report_path, "\n")
