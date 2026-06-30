from __future__ import annotations

import platform
import shutil
import sys
import time
from pathlib import Path

import matplotlib
import numpy as np
import openpyxl
import pandas as pd
import scipy
import statsmodels

import baseline
import correlations
import descriptives
import effectiveness
import pca_analysis
import pre_age_sex
import predictors
import prepare_data
import training_effect
from common import file_sha256, write_workbook
from config import ANALYSIS_ROOT, INPUT_DATABASE, OUTPUT_ROOT


def clean_output() -> None:
    output = OUTPUT_ROOT.resolve()
    analysis = ANALYSIS_ROOT.resolve()
    if output.parent != analysis:
        raise RuntimeError(f"Refusing to clean unexpected output directory: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def significant_count(frame: pd.DataFrame, column: str = "significant_fdr05") -> int:
    if frame is None or frame.empty or column not in frame:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


def write_summary(results: dict, elapsed_seconds: float) -> Path:
    training = results["training"]
    effect = results["effectiveness"]
    predictor = results["predictors"]
    pca = results["pca"]
    correlations_result = results["correlations"]["tidy"]
    pre_covariates = results["pre_age_sex"]["tests"]
    lines = [
        "# Analysis 2 summary",
        "",
        "## Input",
        "",
        f"- Database: `{INPUT_DATABASE.relative_to(INPUT_DATABASE.parents[1])}`",
        f"- SHA-256: `{file_sha256(INPUT_DATABASE)}`",
        "- Participants: 101",
        "- Minefield scores: original database measures with Planning and WM-Planning route efficiency recalculated where raw data are available",
        "",
        "## Analyses completed",
        "",
        f"- PRE/POST variables tested: {len(training['interactions'])}",
        f"- Group x time interactions significant after FDR: {significant_count(training['interactions'])}",
        f"- Age-adjusted group x time interactions significant after FDR: {significant_count(training['interactions'])}",
        f"- Baseline/PRE measures associated with age after FDR: {significant_count(pre_covariates, 'age_significant_fdr05')}",
        f"- Baseline/PRE measures differing by sex after FDR: {significant_count(pre_covariates, 'sex_significant_fdr05')}",
        f"- Effectiveness outcomes: {effect['individual']['variable'].nunique() if not effect['individual'].empty else 0}",
        f"- Effectiveness group comparisons significant after FDR: {significant_count(effect['comparison'])}",
        f"- PRE outcomes predicted by ABAS/BRIEF after FDR: {significant_count(predictor['pre_questionnaire'])}",
        f"- Predictor main effects significant after FDR: {significant_count(predictor['main'])}",
        f"- Predictor moderation effects significant after FDR: {significant_count(predictor['moderation'])}",
        f"- PCA domains completed: {sum(result.get('status') == 'ok' for result in pca['domains'])}",
        f"- Correlation pairs tested: {len(correlations_result)}",
        f"- Spearman correlations significant after FDR: {int(correlations_result.get('spearman_significant_fdr05', pd.Series(dtype=bool)).fillna(False).sum()) if not correlations_result.empty else 0}",
        "",
        "## Method notes",
        "",
        "- Primary training test: linear model on PRE/POST scores with time, group, time x group, and age; standard errors are clustered by participant.",
        "- The time x group term tests whether PRE-to-POST change differs between experimental and control groups after adjusting for age.",
        "- Multiple testing: Benjamini-Hochberg FDR within each result family.",
        "- Minefield composites combine original accuracy with recalculated route-efficiency percentage.",
        "- Effectiveness is calculated only for outcomes with confirmed theoretical bounds.",
        "- PCA is fit on pooled PRE/POST standardized Minefield features; rows with at least 60% observed features are median-imputed.",
        "",
        "## Reproducibility",
        "",
        f"- Runtime: {elapsed_seconds:.1f} seconds",
        "- Run command: `python analysis_2/run_all.py`",
        "- Detailed workbooks and plots are under `analysis_2/output/`.",
    ]
    path = ANALYSIS_ROOT / "analysis_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_manifest(stage_rows: list[dict], elapsed_seconds: float) -> Path:
    generated = sorted(path for path in OUTPUT_ROOT.rglob("*") if path.is_file())
    files = pd.DataFrame(
        [
            {
                "path": str(path.relative_to(ANALYSIS_ROOT)),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in generated
        ]
    )
    environment = pd.DataFrame(
        [
            {"item": "input_database", "value": str(INPUT_DATABASE)},
            {"item": "input_sha256", "value": file_sha256(INPUT_DATABASE)},
            {"item": "python", "value": sys.version},
            {"item": "platform", "value": platform.platform()},
            {"item": "pandas", "value": pd.__version__},
            {"item": "numpy", "value": np.__version__},
            {"item": "scipy", "value": scipy.__version__},
            {"item": "statsmodels", "value": statsmodels.__version__},
            {"item": "matplotlib", "value": matplotlib.__version__},
            {"item": "openpyxl", "value": openpyxl.__version__},
            {"item": "elapsed_seconds", "value": elapsed_seconds},
        ]
    )
    path = OUTPUT_ROOT / "run_manifest.xlsx"
    write_workbook(path, {"stages": pd.DataFrame(stage_rows), "files": files, "environment": environment})
    return path


def run_stage(name: str, function, *args):
    started = time.perf_counter()
    print(f"[{name}] starting", flush=True)
    result = function(*args)
    elapsed = time.perf_counter() - started
    print(f"[{name}] complete in {elapsed:.1f}s", flush=True)
    return result, elapsed


def main() -> None:
    started = time.perf_counter()
    clean_output()
    stages = []
    results = {}

    prepared, elapsed = run_stage("prepare", prepare_data.run)
    stages.append({"stage": "prepare", "status": "complete", "seconds": elapsed})
    df = prepared["data"]

    for name, function in [
        ("descriptives", descriptives.run),
        ("baseline", baseline.run),
        ("pre_age_sex", pre_age_sex.run),
        ("correlations", correlations.run),
        ("training", training_effect.run),
        ("effectiveness", effectiveness.run),
    ]:
        result, elapsed = run_stage(name, function, df)
        results[name] = result
        stages.append({"stage": name, "status": "complete", "seconds": elapsed})

    predictor_result, elapsed = run_stage(
        "predictors",
        predictors.run,
        df,
        results["effectiveness"]["individual"],
    )
    results["predictors"] = predictor_result
    stages.append({"stage": "predictors", "status": "complete", "seconds": elapsed})

    pca_result, elapsed = run_stage("pca", pca_analysis.run, df)
    results["pca"] = pca_result
    stages.append({"stage": "pca", "status": "complete", "seconds": elapsed})

    total_elapsed = time.perf_counter() - started
    summary_path = write_summary(results, total_elapsed)
    manifest_path = write_manifest(stages, total_elapsed)
    print(f"Analysis 2 complete in {total_elapsed:.1f}s", flush=True)
    print(f"Summary: {summary_path}", flush=True)
    print(f"Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
