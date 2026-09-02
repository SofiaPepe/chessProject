# R analysis pipeline

This directory is the R port of `../scripts/`. It preserves the same source
database, Raven screening, complete-case rules, outcome and predictor sets,
standardisation, model formulas, HC3 covariance estimator, FDR families,
diagnostics, aggregate outputs, and paper tables.

## Files

- `config.R`: paths, variables, labels, and prespecified model blocks.
- `analysis_core.R`: data preparation, models, diagnostics, exports, and figures.
- `run_analysis.R`: analysis entry point.
- `render_paper.R`: Quarto DOCX and HTML rendering entry point.
- `verify_parity.R`: end-to-end comparison against the retained Python pipeline.
- `tests/test_analysis.R`: R-native invariants and regression tests.

The parity verifier compares all stable workbook sheets and exported analysis
tables. The software manifest is intentionally not compared because it records
the implementation language and package versions.
