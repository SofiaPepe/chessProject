required_packages <- c(
  "digest", "ggplot2", "openxlsx", "readxl", "sandwich"
)

assert_packages <- function(packages = required_packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) > 0L) {
    stop(
      "Missing required R packages: ", paste(missing, collapse = ", "),
      ". Install them before running this pipeline.",
      call. = FALSE
    )
  }
}

to_numeric_vector <- function(values) {
  if (is.numeric(values)) {
    return(as.numeric(values))
  }
  cleaned <- trimws(as.character(values))
  cleaned <- gsub(",", ".", cleaned, fixed = TRUE)
  cleaned[cleaned %in% c("", "NA", "NaN", "nan", "None")] <- NA_character_
  suppressWarnings(as.numeric(cleaned))
}

file_sha256 <- function(path) {
  digest::digest(file = path, algo = "sha256", serialize = FALSE)
}

safe_clean_generated_directory <- function(target, expected_parent) {
  target_path <- normalizePath(target, winslash = "/", mustWork = FALSE)
  parent_path <- normalizePath(dirname(target), winslash = "/", mustWork = TRUE)
  expected_path <- normalizePath(expected_parent, winslash = "/", mustWork = TRUE)
  if (!identical(parent_path, expected_path)) {
    stop("Refusing to clean unexpected directory: ", target_path, call. = FALSE)
  }
  if (dir.exists(target_path) && unlink(target_path, recursive = TRUE, force = TRUE) != 0L) {
    stop("Unable to clean generated directory: ", target_path, call. = FALSE)
  }
  if (!dir.create(target_path, recursive = TRUE, showWarnings = FALSE) && !dir.exists(target_path)) {
    stop("Unable to create generated directory: ", target_path, call. = FALSE)
  }
}

clean_generated_outputs <- function() {
  safe_clean_generated_directory(OUTPUT_ROOT, SUBPROJECT_ROOT)
  safe_clean_generated_directory(FIGURE_ROOT, SUBPROJECT_ROOT)
  dir.create(TABLE_ROOT, recursive = TRUE, showWarnings = FALSE)
}

required_source_columns <- function() {
  unique(c(
    DEMOGRAPHIC_COLUMNS,
    "Raven_ACC_PRE",
    OUTCOMES$pre_col,
    ABAS_STANDARD_SCALES,
    BRIEF_STANDARD_SCALES,
    BRIEF_INDICES
  ))
}

load_and_prepare <- function() {
  assert_packages()
  if (!file.exists(INPUT_DATABASE)) {
    stop("Input database not found: ", INPUT_DATABASE, call. = FALSE)
  }
  source_data <- as.data.frame(
    readxl::read_excel(INPUT_DATABASE, sheet = INPUT_SHEET, .name_repair = "minimal"),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
  names(source_data) <- trimws(as.character(names(source_data)))
  if (anyDuplicated(source_data$ID) > 0L) {
    stop("Duplicate participant IDs found in source database", call. = FALSE)
  }

  required <- required_source_columns()
  missing <- setdiff(required, names(source_data))
  if (length(missing) > 0L) {
    stop("Required source columns missing: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  selected <- source_data[, required, drop = FALSE]
  forbidden <- names(selected)[
    grepl("_POST$", names(selected), ignore.case = TRUE) |
      tolower(names(selected)) == "group"
  ]
  if (length(forbidden) > 0L) {
    stop("Forbidden columns entered PRE-only analysis: ", paste(forbidden, collapse = ", "), call. = FALSE)
  }

  age <- to_numeric_vector(selected$age)
  raven <- to_numeric_vector(selected$Raven_ACC_PRE)
  cutoff <- unname(RAVEN_CUTOFFS[as.character(age)])
  selected$raven_cutoff <- cutoff
  selected$raven_flag <- !is.na(raven) & !is.na(cutoff) & raven <= cutoff
  if (nrow(selected) != 101L) {
    stop("Expected 101 source participants, found ", nrow(selected), call. = FALSE)
  }
  if (sum(selected$raven_flag) != 2L) {
    stop("Raven screening did not identify exactly two participants", call. = FALSE)
  }

  for (total in names(COMPLETE_TOTALS)) {
    components <- COMPLETE_TOTALS[[total]]
    numeric_components <- as.data.frame(
      lapply(selected[, components, drop = FALSE], to_numeric_vector),
      check.names = FALSE
    )
    observed <- rowSums(!is.na(numeric_components))
    total_values <- rowSums(numeric_components, na.rm = TRUE)
    total_values[observed < length(components)] <- NA_real_
    selected[[total]] <- total_values
    selected[[paste0(total, "_components_observed")]] <- observed
  }

  primary_with_screening <- selected[!selected$raven_flag, , drop = FALSE]
  if (nrow(primary_with_screening) != 99L) {
    stop("Expected primary n=99, found ", nrow(primary_with_screening), call. = FALSE)
  }

  age_values <- sort(unique(to_numeric_vector(selected$age)))
  age_values <- age_values[!is.na(age_values)]
  screening_rows <- lapply(age_values, function(age_value) {
    subset_index <- to_numeric_vector(selected$age) == age_value
    data.frame(
      age = age_value,
      raven_cutoff = unname(RAVEN_CUTOFFS[as.character(age_value)]),
      source_n = sum(subset_index),
      excluded_n = sum(selected$raven_flag[subset_index]),
      included_n = sum(!selected$raven_flag[subset_index]),
      stringsAsFactors = FALSE,
      check.names = FALSE
    )
  })
  screening_summary <- do.call(rbind, screening_rows)

  analysis <- primary_with_screening[
    , setdiff(names(primary_with_screening), c("Raven_ACC_PRE", "raven_cutoff", "raven_flag", "ID")),
    drop = FALSE
  ]
  forbidden_analysis <- names(analysis)[
    grepl("RAVEN", names(analysis), ignore.case = TRUE) |
      grepl("_POST$", names(analysis), ignore.case = TRUE) |
      tolower(names(analysis)) %in% c("group", "id")
  ]
  if (length(forbidden_analysis) > 0L) {
    stop("Forbidden columns in model dataset: ", paste(forbidden_analysis, collapse = ", "), call. = FALSE)
  }

  list(full = selected, analysis = analysis, screening_summary = screening_summary)
}

unbiased_skewness <- function(values) {
  values <- values[!is.na(values)]
  n <- length(values)
  if (n < 3L) return(NA_real_)
  centered <- values - mean(values)
  m2 <- mean(centered^2)
  if (m2 <= 0) return(NA_real_)
  g1 <- mean(centered^3) / (m2^(3 / 2))
  sqrt(n * (n - 1)) / (n - 2) * g1
}

unbiased_excess_kurtosis <- function(values) {
  values <- values[!is.na(values)]
  n <- length(values)
  if (n < 4L) return(NA_real_)
  centered <- values - mean(values)
  m2 <- mean(centered^2)
  if (m2 <= 0) return(NA_real_)
  g2 <- mean(centered^4) / (m2^2) - 3
  ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6)
}

numeric_summary <- function(values) {
  numeric_values <- to_numeric_vector(values)
  observed <- numeric_values[!is.na(numeric_values)]
  c(
    n = length(observed),
    missing = sum(is.na(numeric_values)),
    mean = mean(observed),
    sd = stats::sd(observed),
    median = stats::median(observed),
    q1 = unname(stats::quantile(observed, 0.25, type = 7)),
    q3 = unname(stats::quantile(observed, 0.75, type = 7)),
    minimum = min(observed),
    maximum = max(observed),
    skewness = unbiased_skewness(observed),
    excess_kurtosis = unbiased_excess_kurtosis(observed),
    n_negative = sum(observed < 0)
  )
}

rows_to_data_frame <- function(rows) {
  result <- do.call(rbind, lapply(rows, function(row) {
    as.data.frame(as.list(row), stringsAsFactors = FALSE, check.names = FALSE)
  }))
  rownames(result) <- NULL
  result
}

build_descriptives <- function(full, analysis, screening_summary) {
  age <- to_numeric_vector(analysis$age)
  sex <- toupper(as.character(analysis$sex))
  participants <- data.frame(
    characteristic = c(
      "Source database participants", "Excluded by Raven screening",
      "Primary analytic sample", "Age, mean", "Age, SD", "Age, minimum",
      "Age, maximum", "Male", "Female"
    ),
    value = c(
      nrow(full), nrow(full) - nrow(analysis), nrow(analysis), mean(age),
      stats::sd(age), min(age), max(age), sum(sex == "M"), sum(sex == "F")
    ),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )

  outcome_rows <- lapply(seq_len(nrow(OUTCOMES)), function(index) {
    outcome <- OUTCOMES$outcome[index]
    c(
      variable = outcome,
      label = unname(OUTCOME_LABELS[outcome]),
      family = OUTCOMES$family[index],
      numeric_summary(analysis[[OUTCOMES$pre_col[index]]])
    )
  })
  outcome_descriptives <- rows_to_data_frame(outcome_rows)
  numeric_summary_columns <- c(
    "n", "missing", "mean", "sd", "median", "q1", "q3", "minimum",
    "maximum", "skewness", "excess_kurtosis", "n_negative"
  )
  outcome_descriptives[numeric_summary_columns] <- lapply(
    outcome_descriptives[numeric_summary_columns], as.numeric
  )

  predictor_columns <- c(
    names(COMPLETE_TOTALS), ABAS_STANDARD_SCALES, BRIEF_STANDARD_SCALES,
    BRIEF_INDICES
  )
  predictor_rows <- lapply(predictor_columns, function(predictor) {
    c(
      variable = predictor,
      label = unname(PREDICTOR_LABELS[predictor]),
      family = if (startsWith(predictor, "ABAS")) "ABAS-II" else "BRIEF-2",
      numeric_summary(analysis[[predictor]])
    )
  })
  predictor_descriptives <- rows_to_data_frame(predictor_rows)
  predictor_descriptives[numeric_summary_columns] <- lapply(
    predictor_descriptives[numeric_summary_columns], as.numeric
  )

  outcome_dictionary <- data.frame(
    role = "outcome",
    variable = OUTCOMES$outcome,
    source_column = OUTCOMES$pre_col,
    label = unname(OUTCOME_LABELS[OUTCOMES$outcome]),
    direction = ifelse(
      OUTCOMES$outcome %in% c("TOL_VIO_REG", "PLANNING_EFF", "PWM_EFF"),
      "lower_better", "higher_better"
    ),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
  predictor_dictionary <- data.frame(
    role = "predictor",
    variable = predictor_columns,
    source_column = predictor_columns,
    label = unname(PREDICTOR_LABELS[predictor_columns]),
    direction = ifelse(
      startsWith(predictor_columns, "ABAS"),
      "higher_better", "higher_more_difficulties"
    ),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
  variable_dictionary <- rbind(outcome_dictionary, predictor_dictionary)

  correlation_columns <- c("age", OUTCOMES$pre_col, predictor_columns)
  correlation_input <- as.data.frame(
    lapply(analysis[, correlation_columns, drop = FALSE], to_numeric_vector),
    check.names = FALSE
  )
  correlation_matrix <- stats::cor(
    correlation_input, use = "pairwise.complete.obs", method = "pearson"
  )
  correlations <- data.frame(
    variable = rownames(correlation_matrix),
    correlation_matrix,
    row.names = NULL,
    stringsAsFactors = FALSE,
    check.names = FALSE
  )

  list(
    participants = participants,
    screening_by_age = screening_summary,
    outcome_descriptives = outcome_descriptives,
    predictor_descriptives = predictor_descriptives,
    variable_dictionary = variable_dictionary,
    correlations = correlations
  )
}

zscore <- function(values) {
  values <- to_numeric_vector(values)
  standard_deviation <- stats::sd(values)
  if (is.na(standard_deviation) || standard_deviation <= 0) {
    return(rep(NA_real_, length(values)))
  }
  (values - mean(values)) / standard_deviation
}

hc3_covariance <- function(fit) {
  sandwich::vcovHC(fit, type = "HC3")
}

breusch_pagan_p <- function(fit) {
  residual_squared <- stats::residuals(fit)^2
  design <- stats::model.matrix(fit)
  if (ncol(design) <= 1L) return(NA_real_)
  auxiliary <- stats::lm.fit(design, residual_squared)
  tss <- sum((residual_squared - mean(residual_squared))^2)
  if (tss <= 0) return(NA_real_)
  r_squared <- 1 - sum(auxiliary$residuals^2) / tss
  statistic <- length(residual_squared) * r_squared
  stats::pchisq(statistic, df = ncol(design) - 1L, lower.tail = FALSE)
}

model_diagnostics <- function(fit) {
  cooks <- stats::cooks.distance(fit)
  leverage <- stats::hatvalues(fit)
  studentized <- stats::rstudent(fit)
  residual <- stats::residuals(fit)
  threshold <- 4 / stats::nobs(fit)
  c(
    residual_skewness = unbiased_skewness(residual),
    residual_excess_kurtosis = unbiased_excess_kurtosis(residual),
    max_abs_studentized_residual = max(abs(studentized), na.rm = TRUE),
    max_leverage = max(leverage, na.rm = TRUE),
    max_cooks_distance = max(cooks, na.rm = TRUE),
    cooks_threshold_4_over_n = threshold,
    n_cooks_above_threshold = sum(cooks > threshold, na.rm = TRUE),
    breusch_pagan_p = breusch_pagan_p(fit)
  )
}

focal_vifs <- function(frame, predictors, features) {
  values <- stats::setNames(rep(NA_real_, length(predictors)), predictors)
  if (length(predictors) < 2L) return(values)
  for (predictor in predictors) {
    other_features <- setdiff(features, predictor)
    auxiliary_data <- data.frame(
      y = frame[[predictor]], frame[, other_features, drop = FALSE],
      check.names = FALSE
    )
    auxiliary_fit <- stats::lm(y ~ ., data = auxiliary_data)
    values[predictor] <- 1 / (1 - summary(auxiliary_fit)$r.squared)
  }
  values
}

fit_model <- function(
  analysis, block, model_type, outcome, pre_col, outcome_family, predictors
) {
  required <- c(pre_col, predictors, "age")
  numeric_data <- as.data.frame(
    lapply(analysis[, required, drop = FALSE], to_numeric_vector),
    check.names = FALSE
  )
  complete <- numeric_data[stats::complete.cases(numeric_data), , drop = FALSE]
  base <- list(
    block = block,
    model_type = model_type,
    outcome = outcome,
    outcome_label = unname(OUTCOME_LABELS[outcome]),
    pre_col = pre_col,
    outcome_family = outcome_family,
    n = nrow(complete)
  )
  if (nrow(complete) < MIN_N) {
    return(lapply(predictors, function(predictor) {
      c(base, list(predictor = predictor, status = "insufficient_data"))
    }))
  }

  standardized <- as.data.frame(lapply(complete, zscore), check.names = FALSE)
  if (anyNA(standardized)) {
    return(lapply(predictors, function(predictor) {
      c(base, list(predictor = predictor, status = "zero_variance"))
    }))
  }

  features <- c(predictors, "age")
  model_data <- data.frame(
    outcome_z = standardized[[pre_col]],
    standardized[, features, drop = FALSE],
    check.names = FALSE
  )
  age_data <- data.frame(
    outcome_z = standardized[[pre_col]], age = standardized$age,
    check.names = FALSE
  )

  tryCatch({
    fit <- stats::lm(outcome_z ~ ., data = model_data)
    age_fit <- stats::lm(outcome_z ~ age, data = age_data)
    covariance <- hc3_covariance(fit)
    coefficients <- stats::coef(fit)
    robust_se <- sqrt(diag(covariance))
    diagnostics <- model_diagnostics(fit)
    vifs <- focal_vifs(standardized, predictors, features)
    full_ssr <- sum(stats::residuals(fit)^2)

    lapply(predictors, function(predictor) {
      reduced_features <- setdiff(features, predictor)
      reduced_data <- data.frame(
        outcome_z = standardized[[pre_col]],
        standardized[, reduced_features, drop = FALSE],
        check.names = FALSE
      )
      reduced_fit <- stats::lm(outcome_z ~ ., data = reduced_data)
      reduced_ssr <- sum(stats::residuals(reduced_fit)^2)
      partial_r_squared <- if (reduced_ssr > 0) {
        (reduced_ssr - full_ssr) / reduced_ssr
      } else {
        NA_real_
      }
      beta <- unname(coefficients[predictor])
      standard_error <- unname(robust_se[predictor])
      p_value <- 2 * stats::pnorm(-abs(beta / standard_error))
      fit_summary <- summary(fit)
      age_summary <- summary(age_fit)
      c(
        base,
        list(
          predictor = predictor,
          predictor_label = unname(PREDICTOR_LABELS[predictor]),
          predictor_family = if (startsWith(predictor, "ABAS")) "ABAS-II" else "BRIEF-2",
          status = "ok",
          beta_standardized = beta,
          se_hc3 = standard_error,
          ci_low = beta - stats::qnorm(0.975) * standard_error,
          ci_high = beta + stats::qnorm(0.975) * standard_error,
          p_value = p_value,
          r_squared = fit_summary$r.squared,
          adj_r_squared = fit_summary$adj.r.squared,
          age_only_r_squared = age_summary$r.squared,
          delta_r_squared_vs_age = fit_summary$r.squared - age_summary$r.squared,
          partial_r_squared = partial_r_squared,
          vif = unname(vifs[predictor]),
          formula = paste0(
            "outcome_z ~ ",
            paste(paste0(features, "_z"), collapse = " + ")
          )
        ),
        as.list(diagnostics)
      )
    })
  }, error = function(error) {
    lapply(predictors, function(predictor) {
      c(
        base,
        list(
          predictor = predictor,
          predictor_label = unname(PREDICTOR_LABELS[predictor]),
          status = paste0(class(error)[1], ": ", conditionMessage(error))
        )
      )
    })
  })
}

run_primary_models <- function(analysis) {
  rows <- list()
  row_index <- 1L
  for (outcome_index in seq_len(nrow(OUTCOMES))) {
    outcome <- OUTCOMES$outcome[outcome_index]
    pre_col <- OUTCOMES$pre_col[outcome_index]
    outcome_family <- OUTCOMES$family[outcome_index]
    for (block in names(PREDICTOR_BLOCKS)) {
      for (predictor in PREDICTOR_BLOCKS[[block]]) {
        fitted <- fit_model(
          analysis = analysis,
          block = block,
          model_type = "separate",
          outcome = outcome,
          pre_col = pre_col,
          outcome_family = outcome_family,
          predictors = predictor
        )
        rows[[row_index]] <- fitted[[1]]
        row_index <- row_index + 1L
      }
    }
    joint_rows <- fit_model(
      analysis = analysis,
      block = "totals_joint",
      model_type = "joint",
      outcome = outcome,
      pre_col = pre_col,
      outcome_family = outcome_family,
      predictors = names(COMPLETE_TOTALS)
    )
    for (joint_row in joint_rows) {
      rows[[row_index]] <- joint_row
      row_index <- row_index + 1L
    }
  }

  result <- rows_to_data_frame(rows)
  numeric_columns <- c(
    "n", "beta_standardized", "se_hc3", "ci_low", "ci_high", "p_value",
    "r_squared", "adj_r_squared", "age_only_r_squared",
    "delta_r_squared_vs_age", "partial_r_squared", "vif",
    "residual_skewness", "residual_excess_kurtosis",
    "max_abs_studentized_residual", "max_leverage", "max_cooks_distance",
    "cooks_threshold_4_over_n", "n_cooks_above_threshold",
    "breusch_pagan_p"
  )
  result[numeric_columns] <- lapply(result[numeric_columns], as.numeric)
  result$q_fdr_bh <- NA_real_
  valid <- result$status == "ok" & !is.na(result$p_value)
  for (block in unique(result$block[valid])) {
    index <- which(valid & result$block == block)
    result$q_fdr_bh[index] <- stats::p.adjust(result$p_value[index], method = "BH")
  }
  result$significant_raw_p05 <- result$p_value < ALPHA
  result$significant_fdr05 <- result$q_fdr_bh < ALPHA
  result <- result[
    order(result$block, result$q_fdr_bh, result$p_value, na.last = TRUE),
    , drop = FALSE
  ]
  rownames(result) <- NULL

  ok <- result[result$status == "ok", , drop = FALSE]
  if (nrow(ok) != 216L) {
    stop("Expected 216 model terms, found ", nrow(ok), call. = FALSE)
  }
  observed_sizes <- table(ok$block)
  expected <- EXPECTED_BLOCK_TERMS[names(observed_sizes)]
  if (!identical(as.integer(observed_sizes), as.integer(expected))) {
    stop("Unexpected model block sizes", call. = FALSE)
  }
  if (sum(ok$significant_fdr05) != 22L) {
    stop(
      "Expected 22 FDR-significant terms, found ",
      sum(ok$significant_fdr05), call. = FALSE
    )
  }
  if (any(grepl("Raven|POST|group", ok$formula, ignore.case = TRUE))) {
    stop("Forbidden term found in primary model formula", call. = FALSE)
  }
  result
}

build_block_summary <- function(models) {
  ok <- models[models$status == "ok", , drop = FALSE]
  blocks <- unique(ok$block)
  rows <- lapply(blocks, function(block) {
    subset <- ok[ok$block == block, , drop = FALSE]
    data.frame(
      block = block,
      terms_tested = nrow(subset),
      raw_p05 = sum(subset$significant_raw_p05),
      fdr_q05 = sum(subset$significant_fdr05),
      median_n = stats::median(subset$n),
      minimum_n = min(subset$n),
      maximum_n = max(subset$n),
      stringsAsFactors = FALSE,
      check.names = FALSE
    )
  })
  result <- do.call(rbind, rows)
  rownames(result) <- NULL
  result
}

write_workbook <- function(path, sheets) {
  workbook <- openxlsx::createWorkbook()
  header_style <- openxlsx::createStyle(
    textDecoration = "bold", fgFill = "#D9EAF7"
  )
  for (sheet_name in names(sheets)) {
    safe_name <- substr(sheet_name, 1L, 31L)
    frame <- as.data.frame(sheets[[sheet_name]], stringsAsFactors = FALSE, check.names = FALSE)
    openxlsx::addWorksheet(workbook, safe_name)
    openxlsx::writeData(workbook, safe_name, frame, keepNA = FALSE)
    openxlsx::freezePane(workbook, safe_name, firstRow = TRUE)
    if (ncol(frame) > 0L) {
      openxlsx::addFilter(workbook, safe_name, rows = 1L, cols = seq_len(ncol(frame)))
      openxlsx::addStyle(
        workbook, safe_name, header_style,
        rows = 1L, cols = seq_len(ncol(frame)), gridExpand = TRUE
      )
      widths <- vapply(seq_along(frame), function(index) {
        values <- c(names(frame)[index], as.character(utils::head(frame[[index]], 199L)))
        character_widths <- nchar(values)
        observed_widths <- character_widths[is.finite(character_widths)]
        content_width <- if (length(observed_widths) > 0L) max(observed_widths) else 0L
        min(max(content_width + 2L, 10L), 45L)
      }, numeric(1))
      openxlsx::setColWidths(
        workbook, safe_name, cols = seq_len(ncol(frame)), widths = widths
      )
    }
  }
  openxlsx::saveWorkbook(workbook, path, overwrite = TRUE)
}

format_p <- function(value) {
  if (is.na(value)) return("")
  if (value < 0.001) return("<.001")
  sub("^0", "", sprintf("%.3f", value))
}

markdown_table <- function(frame, columns) {
  if (nrow(frame) == 0L) return("No results met the specified criterion.")
  headers <- unname(columns)
  source_columns <- names(columns)
  lines <- c(
    paste0("| ", paste(headers, collapse = " | "), " |"),
    paste0("|", paste(rep("---", length(headers)), collapse = "|"), "|")
  )
  body <- vapply(seq_len(nrow(frame)), function(row_index) {
    values <- vapply(source_columns, function(column) {
      value <- frame[[column]][row_index]
      if (is.na(value)) "" else as.character(value)
    }, character(1))
    paste0("| ", paste(values, collapse = " | "), " |")
  }, character(1))
  paste(c(lines, body), collapse = "\n")
}

paper_result_table <- function(models) {
  table <- models[!is.na(models$significant_fdr05) & models$significant_fdr05, , drop = FALSE]
  table$n_fmt <- as.character(as.integer(table$n))
  table$beta_fmt <- sprintf("%.3f", table$beta_standardized)
  table$ci_fmt <- sprintf("[%.3f, %.3f]", table$ci_low, table$ci_high)
  table$p_fmt <- vapply(table$p_value, format_p, character(1))
  table$q_fmt <- vapply(table$q_fdr_bh, format_p, character(1))
  table$partial_r2_fmt <- sprintf("%.3f", table$partial_r_squared)
  table$delta_r2_fmt <- sprintf("%.3f", table$delta_r_squared_vs_age)
  table
}

write_text_utf8 <- function(text, path) {
  connection <- file(path, open = "wb")
  on.exit(close(connection), add = TRUE)
  writeBin(charToRaw(enc2utf8(text)), connection)
}

write_paper_tables <- function(descriptives, models, block_summary) {
  dir.create(TABLE_ROOT, recursive = TRUE, showWarnings = FALSE)

  participants <- descriptives$participants
  participants$value_fmt <- sprintf("%.2f", participants$value)
  participant_md <- markdown_table(
    participants,
    c(characteristic = "Characteristic", value_fmt = "Value")
  )

  outcomes <- descriptives$outcome_descriptives
  for (column in c("mean", "sd", "median", "minimum", "maximum")) {
    outcomes[[paste0(column, "_fmt")]] <- sprintf("%.2f", outcomes[[column]])
  }
  outcome_md <- markdown_table(
    outcomes,
    c(
      label = "Outcome", n = "n", missing = "Missing", mean_fmt = "Mean",
      sd_fmt = "SD", median_fmt = "Median", minimum_fmt = "Min",
      maximum_fmt = "Max"
    )
  )

  summary <- block_summary
  summary$median_n_fmt <- sprintf("%.0f", summary$median_n)
  block_md <- markdown_table(
    summary,
    c(
      block = "FDR family", terms_tested = "Terms", raw_p05 = "Raw p<.05",
      fdr_q05 = "FDR q<.05", median_n_fmt = "Median n"
    )
  )

  paper_results <- paper_result_table(models)
  totals <- paper_results[
    paper_results$block %in% c("totals_separate", "totals_joint"), , drop = FALSE
  ]
  secondary <- paper_results[
    paper_results$block %in% c("abas_subscales", "brief_subscales", "brief_indices"),
    , drop = FALSE
  ]
  result_columns <- c(
    predictor_label = "Predictor", outcome_label = "Outcome", n_fmt = "n",
    beta_fmt = "\u03b2", ci_fmt = "95% CI", p_fmt = "p", q_fmt = "q",
    delta_r2_fmt = "\u0394R\u00b2", partial_r2_fmt = "Partial R\u00b2"
  )
  totals_md <- markdown_table(totals, result_columns)
  secondary_md <- markdown_table(secondary, result_columns)

  planning_count <- sum(paper_results$outcome == "PLANNING_ACC")
  narrative <- c(
    "The screened analytic sample comprised 99 children. Across the five prespecified ",
    "FDR families, 216 questionnaire coefficient tests were estimated and 22 survived ",
    "Benjamini\u2013Hochberg correction. These coefficients should not be interpreted as ",
    "22 independent phenomena because correlated questionnaire scales frequently mapped ",
    "onto the same cognitive outcomes.",
    "",
    paste0(
      "Five FDR-significant associations involved questionnaire total scores, and ",
      nrow(secondary), " involved subscales or BRIEF-2 indices."
    ),
    "",
    paste0(
      "Planning accuracy was associated with ", planning_count,
      " questionnaire predictors after FDR correction. No FDR-significant association ",
      "was observed for either excess-tile outcome, PWM accuracy, or Corsi forward span."
    )
  )

  content <- list(
    table1_participants.md = paste0(participant_md, "\n"),
    table2_outcomes.md = paste0(outcome_md, "\n"),
    table3_block_summary.md = paste0(block_md, "\n"),
    table4_totals.md = paste0(totals_md, "\n"),
    table5_subscales_indices.md = paste0(secondary_md, "\n"),
    results_narrative.md = paste0(paste(narrative, collapse = "\n"), "\n")
  )
  paths <- character()
  for (name in names(content)) {
    path <- file.path(TABLE_ROOT, name)
    write_text_utf8(content[[name]], path)
    paths <- c(paths, path)
  }
  paths
}

create_figures <- function(models) {
  dir.create(FIGURE_ROOT, recursive = TRUE, showWarnings = FALSE)
  significant <- models[
    !is.na(models$significant_fdr05) & models$significant_fdr05, , drop = FALSE
  ]
  significant$association <- paste0(
    significant$predictor_label, " \u2192 ", significant$outcome_label
  )
  significant <- significant[
    order(significant$outcome_label, significant$beta_standardized), , drop = FALSE
  ]

  significant$association_plot <- factor(
    significant$association, levels = rev(significant$association)
  )
  forest <- ggplot2::ggplot(
    significant,
    ggplot2::aes(
      x = beta_standardized, y = association_plot,
      colour = predictor_family
    )
  ) +
    ggplot2::geom_vline(xintercept = 0, colour = "black", linewidth = 0.35) +
    ggplot2::geom_errorbar(
      ggplot2::aes(xmin = ci_low, xmax = ci_high),
      orientation = "y", width = 0.18, linewidth = 0.45
    ) +
    ggplot2::geom_point(size = 2) +
    ggplot2::scale_colour_manual(values = c("ABAS-II" = "#2878B5", "BRIEF-2" = "#D95F02")) +
    ggplot2::labs(
      x = "Standardized coefficient \u03b2 (95% CI)", y = NULL,
      title = "FDR-significant age-adjusted associations", colour = NULL
    ) +
    ggplot2::theme_bw(base_size = 10) +
    ggplot2::theme(
      panel.grid.minor = ggplot2::element_blank(),
      axis.text.y = ggplot2::element_text(size = 8),
      legend.position = "bottom"
    )
  forest_height <- max(8, nrow(significant) * 0.42)
  forest_png <- file.path(FIGURE_ROOT, "primary_forest_plot.png")
  forest_svg <- file.path(FIGURE_ROOT, "primary_forest_plot.svg")
  ggplot2::ggsave(forest_png, forest, width = 10, height = forest_height, units = "in", dpi = 300)
  grDevices::svg(forest_svg, width = 10, height = forest_height)
  print(forest)
  grDevices::dev.off()

  predictor_levels <- sort(unique(significant$predictor_label))
  outcome_levels <- sort(unique(significant$outcome_label))
  heat_grid <- expand.grid(
    predictor_label = predictor_levels,
    outcome_label = outcome_levels,
    stringsAsFactors = FALSE
  )
  heat_grid <- merge(
    heat_grid,
    significant[, c("predictor_label", "outcome_label", "beta_standardized")],
    by = c("predictor_label", "outcome_label"), all.x = TRUE, sort = FALSE
  )
  heat_grid$predictor_plot <- factor(
    heat_grid$predictor_label, levels = rev(predictor_levels)
  )
  heat_grid$outcome_plot <- factor(heat_grid$outcome_label, levels = outcome_levels)
  heat_grid$label <- ifelse(
    is.na(heat_grid$beta_standardized), "", sprintf("%.2f", heat_grid$beta_standardized)
  )
  heat <- ggplot2::ggplot(
    heat_grid,
    ggplot2::aes(x = outcome_plot, y = predictor_plot, fill = beta_standardized)
  ) +
    ggplot2::geom_tile(colour = "white", linewidth = 0.5) +
    ggplot2::geom_text(ggplot2::aes(label = label), size = 3) +
    ggplot2::scale_fill_gradient2(
      low = "#3B4CC0", mid = "white", high = "#B40426",
      midpoint = 0, na.value = "white", name = "Standardized \u03b2"
    ) +
    ggplot2::labs(
      x = NULL, y = NULL, title = "FDR-significant predictor\u2013outcome map"
    ) +
    ggplot2::theme_minimal(base_size = 10) +
    ggplot2::theme(
      panel.grid = ggplot2::element_blank(),
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
      axis.text.y = ggplot2::element_text(size = 8)
    )
  heat_width <- max(8, length(outcome_levels) * 1.7)
  heat_height <- max(6, length(predictor_levels) * 0.45)
  heat_png <- file.path(FIGURE_ROOT, "significant_beta_heatmap.png")
  heat_svg <- file.path(FIGURE_ROOT, "significant_beta_heatmap.svg")
  ggplot2::ggsave(heat_png, heat, width = heat_width, height = heat_height, units = "in", dpi = 300)
  grDevices::svg(heat_svg, width = heat_width, height = heat_height)
  print(heat)
  grDevices::dev.off()

  c(forest_png, forest_svg, heat_png, heat_svg)
}

write_summary <- function(descriptives, models, block_summary) {
  outcomes <- descriptives$outcome_descriptives
  planning_negative <- outcomes$n_negative[outcomes$variable == "PLANNING_EFF"]
  pwm_negative <- outcomes$n_negative[outcomes$variable == "PWM_EFF"]
  summary_table <- markdown_table(
    transform(
      block_summary,
      terms_tested = as.character(terms_tested),
      raw_p05 = as.character(raw_p05),
      fdr_q05 = as.character(fdr_q05),
      median_n = as.character(median_n),
      minimum_n = as.character(minimum_n),
      maximum_n = as.character(maximum_n)
    ),
    c(
      block = "block", terms_tested = "terms_tested", raw_p05 = "raw_p05",
      fdr_q05 = "fdr_q05", median_n = "median_n", minimum_n = "minimum_n",
      maximum_n = "maximum_n"
    )
  )
  lines <- c(
    "# ABAS-II/BRIEF-2 PRE-only analysis",
    "",
    "- Source participants: 101",
    "- Raven-screened exclusions: 2",
    "- Primary analytic sample: 99",
    "- PRE-only outcomes: 9",
    "- Model terms tested: 216",
    paste0("- FDR-significant model terms: ", sum(models$significant_fdr05, na.rm = TRUE)),
    paste0("- Negative PLANNING_EFF observations retained: ", planning_negative),
    paste0("- Negative PWM_EFF observations retained: ", pwm_negative),
    "- Model: standardized outcome ~ standardized questionnaire predictor + standardized age",
    "- Standard errors: HC3",
    "- Multiple testing: Benjamini\u2013Hochberg within five prespecified blocks",
    "- No POST, training group, Raven covariate, or sensitivity model was used.",
    "",
    "## Block counts",
    "",
    summary_table
  )
  path <- file.path(OUTPUT_ROOT, "analysis_summary.md")
  write_text_utf8(paste0(paste(lines, collapse = "\n"), "\n"), path)
  path
}

write_csv_utf8 <- function(frame, path) {
  csv_frame <- frame
  logical_columns <- vapply(csv_frame, is.logical, logical(1))
  csv_frame[logical_columns] <- lapply(csv_frame[logical_columns], function(values) {
    ifelse(is.na(values), NA_character_, ifelse(values, "True", "False"))
  })
  utils::write.table(
    csv_frame, file = path, sep = ",", row.names = FALSE, col.names = TRUE,
    quote = TRUE, na = "", qmethod = "double", fileEncoding = "UTF-8"
  )
}

run_analysis <- function() {
  assert_packages()
  set.seed(RANDOM_SEED)
  clean_generated_outputs()
  prepared <- load_and_prepare()
  descriptives <- build_descriptives(
    prepared$full, prepared$analysis, prepared$screening_summary
  )
  models <- run_primary_models(prepared$analysis)
  block_summary <- build_block_summary(models)
  significant <- models[
    !is.na(models$significant_fdr05) & models$significant_fdr05, , drop = FALSE
  ]
  diagnostic_columns <- c(
    "block", "predictor", "outcome", "n", "residual_skewness",
    "residual_excess_kurtosis", "max_abs_studentized_residual",
    "max_leverage", "max_cooks_distance", "cooks_threshold_4_over_n",
    "n_cooks_above_threshold", "breusch_pagan_p", "vif"
  )
  diagnostics <- significant[, diagnostic_columns, drop = FALSE]

  manifest <- data.frame(
    item = c(
      "input_database", "input_sha256", "generated_utc", "source_n",
      "raven_excluded_n", "primary_n", "outcomes", "model_terms",
      "fdr_significant_terms", "scope", "r", "platform", "readxl",
      "openxlsx", "sandwich", "ggplot2"
    ),
    value = c(
      "data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx",
      file_sha256(INPUT_DATABASE),
      format(Sys.time(), tz = "UTC", usetz = TRUE),
      nrow(prepared$full), nrow(prepared$full) - nrow(prepared$analysis),
      nrow(prepared$analysis), nrow(OUTCOMES), sum(models$status == "ok"),
      sum(models$significant_fdr05, na.rm = TRUE),
      "PRE-only; Raven screening only; no sensitivity analyses",
      R.version.string, paste(Sys.info()[c("sysname", "release", "machine")], collapse = " "),
      as.character(utils::packageVersion("readxl")),
      as.character(utils::packageVersion("openxlsx")),
      as.character(utils::packageVersion("sandwich")),
      as.character(utils::packageVersion("ggplot2"))
    ),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )

  workbook <- file.path(OUTPUT_ROOT, "analysis_results.xlsx")
  write_workbook(
    workbook,
    list(
      manifest = manifest,
      participants = descriptives$participants,
      screening_by_age = descriptives$screening_by_age,
      variable_dictionary = descriptives$variable_dictionary,
      outcome_descriptives = descriptives$outcome_descriptives,
      predictor_descriptives = descriptives$predictor_descriptives,
      correlations = descriptives$correlations,
      model_results = models,
      block_summary = block_summary,
      significant_results = significant,
      significant_diagnostics = diagnostics
    )
  )

  write_csv_utf8(models, file.path(TABLE_ROOT, "all_primary_models.csv"))
  write_csv_utf8(significant, file.path(TABLE_ROOT, "fdr_significant_models.csv"))
  write_csv_utf8(
    descriptives$outcome_descriptives,
    file.path(TABLE_ROOT, "outcome_descriptives.csv")
  )
  write_csv_utf8(block_summary, file.path(TABLE_ROOT, "block_summary.csv"))
  write_csv_utf8(
    diagnostics, file.path(TABLE_ROOT, "significant_model_diagnostics.csv")
  )
  paper_files <- write_paper_tables(descriptives, models, block_summary)
  figure_files <- create_figures(models)
  summary <- write_summary(descriptives, models, block_summary)

  list(
    full = prepared$full,
    analysis = prepared$analysis,
    descriptives = descriptives,
    models = models,
    block_summary = block_summary,
    files = c(workbook, summary, paper_files, figure_files)
  )
}
