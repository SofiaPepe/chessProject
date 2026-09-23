script_argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_argument) != 1L) {
  stop("Unable to determine render_paper.R location", call. = FALSE)
}
SCRIPT_ROOT <- dirname(normalizePath(sub("^--file=", "", script_argument), winslash = "/"))
source(file.path(SCRIPT_ROOT, "config.R"), local = FALSE, encoding = "UTF-8")

quarto <- Sys.which("quarto")
if (!nzchar(quarto)) {
  stop("Quarto is not installed or not available on PATH", call. = FALSE)
}
source_path <- file.path(PAPER_ROOT, "abasbrief_paper.qmd")
if (!file.exists(source_path)) {
  stop("Paper source not found: ", source_path, call. = FALSE)
}
required <- c(
  file.path(OUTPUT_ROOT, "analysis_results.xlsx"),
  file.path(TABLE_ROOT, "results_narrative.md"),
  file.path(FIGURE_ROOT, "primary_forest_plot.png")
)
missing <- required[!file.exists(required)]
if (length(missing) > 0L) {
  stop(
    "Analysis outputs are missing; run scripts_r/run_analysis.R first: ",
    paste(missing, collapse = ", "), call. = FALSE
  )
}
word_locks <- list.files(
  PAPER_ROOT, pattern = "^~\\$.*\\.docx$", full.names = TRUE,
  ignore.case = TRUE
)
if (length(word_locks) > 0L) {
  stop("Close abasbrief_paper.docx in Word before rendering it", call. = FALSE)
}

cache_root <- tempfile(pattern = ".quarto_render_r_", tmpdir = OUTPUT_ROOT)
dir.create(cache_root, recursive = TRUE, showWarnings = FALSE)
on.exit({
  cache_path <- normalizePath(cache_root, winslash = "/", mustWork = FALSE)
  output_path <- normalizePath(OUTPUT_ROOT, winslash = "/", mustWork = TRUE)
  if (startsWith(cache_path, paste0(output_path, "/"))) {
    unlink(cache_path, recursive = TRUE, force = TRUE)
  }
}, add = TRUE)
local_app_data <- file.path(cache_root, "local")
roaming_app_data <- file.path(cache_root, "roaming")
deno_dir <- file.path(cache_root, "deno")
dir.create(local_app_data, recursive = TRUE, showWarnings = FALSE)
dir.create(roaming_app_data, recursive = TRUE, showWarnings = FALSE)
dir.create(deno_dir, recursive = TRUE, showWarnings = FALSE)

environment_names <- c("LOCALAPPDATA", "APPDATA", "DENO_DIR")
old_environment <- Sys.getenv(environment_names, unset = NA_character_)
on.exit({
  for (name in environment_names) {
    if (is.na(old_environment[[name]])) {
      Sys.unsetenv(name)
    } else {
      do.call(Sys.setenv, stats::setNames(list(old_environment[[name]]), name))
    }
  }
}, add = TRUE)
do.call(
  Sys.setenv,
  list(
    LOCALAPPDATA = local_app_data,
    APPDATA = roaming_app_data,
    DENO_DIR = deno_dir
  )
)

old_directory <- getwd()
on.exit(setwd(old_directory), add = TRUE)
setwd(PROJECT_ROOT)
status <- system2(
  quarto,
  args = c("render", shQuote(source_path)),
  stdout = "",
  stderr = ""
)
if (!identical(status, 0L)) {
  stop("Quarto rendering failed with exit status ", status, call. = FALSE)
}

expected <- c(
  file.path(PAPER_ROOT, "abasbrief_paper.html"),
  file.path(PAPER_ROOT, "abasbrief_paper.docx")
)
missing_rendered <- expected[!file.exists(expected)]
if (length(missing_rendered) > 0L) {
  stop("Expected rendered files missing: ", paste(missing_rendered, collapse = ", "), call. = FALSE)
}
cat(paste("Rendered:", expected), sep = "\n")
