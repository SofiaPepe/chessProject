from __future__ import annotations

import platform
import shutil
import sys
import time
import warnings
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent
SUBPROJECT_ROOT = ANALYSIS_DIR.parent
PROJECT_ROOT = SUBPROJECT_ROOT.parent
ANALYSIS_2_ROOT = PROJECT_ROOT / "analysis_2"
if str(ANALYSIS_2_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_2_ROOT))

import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.formula.api as smf
from scipy import stats

import config as analysis2_config
from common import (
    build_analysis_dataset,
    fdr_bh,
    file_sha256,
    find_prepost_pairs,
    numeric_summary,
    to_numeric,
    write_workbook,
)
import paper_config as cfg
import dedicated_models


def clean_output() -> None:
    output = cfg.OUTPUT_ROOT.resolve()
    subproject = cfg.SUBPROJECT_ROOT.resolve()
    if output.parent != subproject:
        raise RuntimeError(f"Refusing to clean unexpected output directory: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def outcome_family(variable: str) -> str:
    upper = str(variable).upper()
    if upper.startswith("WM_"):
        return "minefield_working_memory"
    if upper.startswith("PLANNING_"):
        return "minefield_planning"
    if upper.startswith("PWM_"):
        return "minefield_planning_working_memory"
    if upper.startswith("TOL_"):
        return "tower_of_london"
    if upper.startswith("CBT_"):
        return "corsi_block_tapping"
    if upper.startswith("RAVEN"):
        return "raven"
    return "other"


def questionnaire_family(variable: str) -> str:
    if str(variable).startswith("ABAS_"):
        return "ABAS"
    if str(variable).startswith("BRIEF_"):
        return "BRIEF"
    return "other"


def questionnaire_role(variable: str) -> str:
    name = str(variable)
    if name in {"ABAS_TOT", "ABAS_ASSUMED_TOTAL", "BRIEF_TOT"}:
        return "derived_total"
    if name in {"BRIEF_BRI", "BRIEF_ERI", "BRIEF_CRI"}:
        return "index"
    if "supp" in name.lower():
        return "supplemental"
    return "scale"


def zscore(series: pd.Series) -> pd.Series:
    values = to_numeric(series)
    sd = values.std(ddof=1)
    if pd.isna(sd) or sd <= 0:
        return pd.Series(np.nan, index=series.index)
    return (values - values.mean()) / sd


def _usable_numeric(values: pd.Series, min_n: int = cfg.MIN_N) -> bool:
    numeric = to_numeric(values)
    return numeric.notna().sum() >= min_n and numeric.nunique(dropna=True) > 1


def outcome_specs(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pair in find_prepost_pairs(df):
        pre_col = pair["pre_col"]
        values = to_numeric(df[pre_col])
        rows.append(
            {
                "outcome": pair["variable"],
                "pre_col": pre_col,
                "post_col_source": pair["post_col"],
                "domain": pair["domain"],
                "outcome_family": outcome_family(pair["variable"]),
                "transformation": pair["transformation"],
                "n_nonmissing": int(values.notna().sum()),
                "missing": int(values.isna().sum()),
                "unique_nonmissing": int(values.nunique(dropna=True)),
                "usable_for_analysis": bool(_usable_numeric(values)),
            }
        )
    return pd.DataFrame(rows).sort_values(["domain", "outcome_family", "outcome"])


def questionnaire_specs(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in sorted(c for c in df.columns if str(c).startswith(("ABAS_", "BRIEF_"))):
        values = to_numeric(df[column])
        rows.append(
            {
                "questionnaire": column,
                "family": questionnaire_family(column),
                "role": questionnaire_role(column),
                "n_nonmissing": int(values.notna().sum()),
                "missing": int(values.isna().sum()),
                "unique_nonmissing": int(values.nunique(dropna=True)),
                "usable_for_models": bool(_usable_numeric(values)),
            }
        )
    return pd.DataFrame(rows).sort_values(["family", "role", "questionnaire"])


def build_baseline_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    full = build_analysis_dataset()
    outcomes = outcome_specs(full)
    questionnaires = questionnaire_specs(full)
    columns = [
        column for column in cfg.DEMOGRAPHIC_COLUMNS if column in full.columns
    ]
    columns.extend(outcomes["pre_col"].tolist())
    columns.extend(questionnaires["questionnaire"].tolist())
    columns = list(dict.fromkeys(columns))
    post_columns = [column for column in columns if str(column).upper().endswith("_POST")]
    if post_columns:
        raise RuntimeError(f"POST columns are not allowed in this paper dataset: {post_columns}")
    dataset = full[columns].copy()
    return dataset, outcomes, questionnaires


def write_dataset(
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
) -> list[Path]:
    out_dir = cfg.OUTPUT_ROOT / "00_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx = out_dir / "baseline_pre_dataset.xlsx"
    csv = out_dir / "baseline_pre_dataset.csv"
    manifest = pd.DataFrame(
        [
            {"item": "input_database", "value": str(analysis2_config.INPUT_DATABASE)},
            {"item": "input_sheet", "value": analysis2_config.INPUT_SHEET},
            {"item": "participants", "value": len(dataset)},
            {"item": "unique_ids", "value": dataset["ID"].nunique()},
            {"item": "columns", "value": len(dataset.columns)},
            {"item": "pre_outcomes", "value": len(outcomes)},
            {"item": "questionnaires", "value": len(questionnaires)},
            {"item": "min_n_for_models", "value": cfg.MIN_N},
            {"item": "scope", "value": "Baseline PRE only; group and POST columns excluded."},
        ]
    )
    write_workbook(
        xlsx,
        {
            "baseline_pre_dataset": dataset,
            "pre_outcome_dictionary": outcomes,
            "questionnaire_dictionary": questionnaires,
            "manifest": manifest,
        },
    )
    dataset.to_csv(csv, index=False, encoding="utf-8-sig")
    return [xlsx, csv]


def run_descriptives(
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
) -> dict:
    out_dir = cfg.OUTPUT_ROOT / "01_descriptives"
    numeric_columns = ["age"]
    numeric_columns.extend(outcomes["pre_col"].tolist())
    numeric_columns.extend(questionnaires["questionnaire"].tolist())
    numeric_columns = [c for c in dict.fromkeys(numeric_columns) if c in dataset]
    overall = pd.DataFrame(
        [{"variable": column, **numeric_summary(dataset[column])} for column in numeric_columns]
    )
    missingness = pd.DataFrame(
        [
            {
                "variable": column,
                "n_nonmissing": int(dataset[column].notna().sum()),
                "missing": int(dataset[column].isna().sum()),
                "missing_pct": float(dataset[column].isna().mean() * 100),
                "unique_nonmissing": int(dataset[column].nunique(dropna=True)),
            }
            for column in dataset.columns
        ]
    ).sort_values(["missing_pct", "variable"], ascending=[False, True])
    composition_rows = []
    for column in ["sex", "age", "class", "section", "hand", "semestre"]:
        if column not in dataset:
            continue
        counts = dataset[column].value_counts(dropna=False)
        for level, count in counts.items():
            composition_rows.append(
                {
                    "variable": column,
                    "level": level,
                    "count": int(count),
                    "percent": float(count / len(dataset) * 100),
                }
            )
    sample_composition = pd.DataFrame(composition_rows)
    path = out_dir / "descriptives.xlsx"
    write_workbook(
        path,
        {
            "overall_numeric": overall,
            "missingness": missingness,
            "sample_composition": sample_composition,
            "pre_outcome_dictionary": outcomes,
            "questionnaire_dictionary": questionnaires,
        },
    )
    return {"overall": overall, "missingness": missingness, "files": [path]}


def run_correlations(
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
) -> dict:
    usable_outcomes = outcomes.loc[outcomes["usable_for_analysis"]].copy()
    usable_questionnaires = questionnaires.loc[questionnaires["usable_for_models"]].copy()
    rows = []
    for _, predictor in usable_questionnaires.iterrows():
        for _, outcome in usable_outcomes.iterrows():
            predictor_col = predictor["questionnaire"]
            outcome_col = outcome["pre_col"]
            data = pd.DataFrame(
                {
                    "predictor": to_numeric(dataset[predictor_col]),
                    "outcome": to_numeric(dataset[outcome_col]),
                }
            ).dropna()
            base = {
                "questionnaire": predictor_col,
                "questionnaire_family": predictor["family"],
                "questionnaire_role": predictor["role"],
                "outcome": outcome["outcome"],
                "pre_col": outcome_col,
                "domain": outcome["domain"],
                "outcome_family": outcome["outcome_family"],
                "transformation": outcome["transformation"],
                "n": len(data),
            }
            if len(data) < cfg.MIN_N or data["predictor"].nunique() < 2 or data["outcome"].nunique() < 2:
                rows.append({**base, "status": "insufficient_data"})
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    pearson_r, pearson_p = stats.pearsonr(data["predictor"], data["outcome"])
                    spearman_rho, spearman_p = stats.spearmanr(data["predictor"], data["outcome"])
                rows.append(
                    {
                        **base,
                        "status": "ok",
                        "pearson_r": pearson_r,
                        "pearson_p": pearson_p,
                        "spearman_rho": spearman_rho,
                        "spearman_p": spearman_p,
                    }
                )
            except Exception as exc:
                rows.append({**base, "status": f"{type(exc).__name__}: {exc}"})

    result = pd.DataFrame(rows)
    result = fdr_bh(result, "spearman_p", "spearman_q_fdr_bh")
    result = fdr_bh(result, "pearson_p", "pearson_q_fdr_bh")
    if not result.empty:
        result["spearman_significant_fdr05"] = result["spearman_q_fdr_bh"] < cfg.ALPHA
        result["pearson_significant_fdr05"] = result["pearson_q_fdr_bh"] < cfg.ALPHA
        result["any_significant_fdr05"] = (
            result["spearman_significant_fdr05"].fillna(False)
            | result["pearson_significant_fdr05"].fillna(False)
        )
        result["absolute_spearman_rho"] = result["spearman_rho"].abs()
        result = result.sort_values(
            ["any_significant_fdr05", "spearman_q_fdr_bh", "absolute_spearman_rho"],
            ascending=[False, True, False],
        )
    significant_any = result.loc[result.get("any_significant_fdr05", False).fillna(False)].copy()
    significant_spearman = result.loc[result.get("spearman_significant_fdr05", False).fillna(False)].copy()
    significant_pearson = result.loc[result.get("pearson_significant_fdr05", False).fillna(False)].copy()
    path = cfg.OUTPUT_ROOT / "02_correlations" / "abas_brief_pre_correlations.xlsx"
    write_workbook(
        path,
        {
            "all_correlations": result,
            "significant_any_fdr05": significant_any,
            "significant_spearman_fdr05": significant_spearman,
            "significant_pearson_fdr05": significant_pearson,
            "minefield_significant": significant_any.loc[significant_any["domain"].eq("minefield")],
        },
    )
    return {
        "all": result,
        "significant_any": significant_any,
        "significant_spearman": significant_spearman,
        "significant_pearson": significant_pearson,
        "files": [path],
    }


def fit_questionnaire_models(
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
    *,
    include_raven: bool = False,
) -> pd.DataFrame:
    usable_outcomes = outcomes.loc[outcomes["usable_for_analysis"]].copy()
    usable_questionnaires = questionnaires.loc[questionnaires["usable_for_models"]].copy()
    rows = []
    for _, predictor in usable_questionnaires.iterrows():
        for _, outcome in usable_outcomes.iterrows():
            predictor_col = predictor["questionnaire"]
            outcome_col = outcome["pre_col"]
            base = {
                "questionnaire": predictor_col,
                "questionnaire_family": predictor["family"],
                "questionnaire_role": predictor["role"],
                "outcome": outcome["outcome"],
                "pre_col": outcome_col,
                "domain": outcome["domain"],
                "outcome_family": outcome["outcome_family"],
                "transformation": outcome["transformation"],
                "model": cfg.RAVEN_MODEL_LABEL if include_raven else cfg.PRIMARY_MODEL_LABEL,
            }
            if include_raven and outcome["outcome_family"] == "raven":
                rows.append({**base, "n": np.nan, "status": "skipped_outcome_is_raven"})
                continue
            columns = [predictor_col, outcome_col, "age"]
            if include_raven:
                columns.append("Raven_ACC_PRE")
            data = dataset[columns].copy()
            data["predictor_z"] = zscore(data[predictor_col])
            data["outcome_z"] = zscore(data[outcome_col])
            data["age_z"] = zscore(data["age"])
            required = ["predictor_z", "outcome_z", "age_z"]
            formula = "outcome_z ~ predictor_z + age_z"
            if include_raven:
                data["raven_pre_z"] = zscore(data["Raven_ACC_PRE"])
                required.append("raven_pre_z")
                formula = "outcome_z ~ predictor_z + age_z + raven_pre_z"
            data = data.dropna(subset=required)
            base["n"] = len(data)
            if len(data) < cfg.MIN_N:
                rows.append({**base, "status": "insufficient_data"})
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = smf.ols(formula, data=data).fit(cov_type="HC3")
                ci = fit.conf_int().loc["predictor_z"]
                rows.append(
                    {
                        **base,
                        "status": "ok",
                        "term": "predictor_z",
                        "beta_standardized": fit.params["predictor_z"],
                        "se_hc3": fit.bse["predictor_z"],
                        "ci_low": ci.iloc[0],
                        "ci_high": ci.iloc[1],
                        "p_value": fit.pvalues["predictor_z"],
                        "r_squared": fit.rsquared,
                        "adj_r_squared": fit.rsquared_adj,
                    }
                )
            except Exception as exc:
                rows.append({**base, "status": f"{type(exc).__name__}: {exc}"})
    result = fdr_bh(pd.DataFrame(rows), "p_value")
    if not result.empty:
        result["significant_p05"] = result["p_value"] < cfg.ALPHA
        result["significant_fdr05"] = result["q_fdr_bh"] < cfg.ALPHA
        result = result.sort_values(
            ["significant_fdr05", "q_fdr_bh", "p_value"],
            ascending=[False, True, True],
        )
    return result


def run_regressions(
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
) -> dict:
    primary = fit_questionnaire_models(dataset, outcomes, questionnaires, include_raven=False)
    raven = fit_questionnaire_models(dataset, outcomes, questionnaires, include_raven=True)
    significant_primary = primary.loc[primary.get("significant_fdr05", False).fillna(False)].copy()
    significant_raven = raven.loc[raven.get("significant_fdr05", False).fillna(False)].copy()
    minefield_focus = primary.loc[primary["domain"].eq("minefield") & primary["status"].eq("ok")].copy()
    minefield_focus = fdr_bh(minefield_focus, "p_value", "q_fdr_bh_minefield_focus")
    if not minefield_focus.empty:
        minefield_focus["significant_minefield_fdr05"] = (
            minefield_focus["q_fdr_bh_minefield_focus"] < cfg.ALPHA
        )
        minefield_focus = minefield_focus.sort_values(
            ["significant_minefield_fdr05", "q_fdr_bh_minefield_focus", "p_value"],
            ascending=[False, True, True],
        )
    minefield_significant = minefield_focus.loc[
        minefield_focus.get("significant_minefield_fdr05", False).fillna(False)
    ].copy()
    family_summary = build_family_summary(primary, raven, minefield_focus)
    path = cfg.OUTPUT_ROOT / "03_regressions" / "abas_brief_pre_regressions.xlsx"
    write_workbook(
        path,
        {
            "primary_age_adjusted": primary,
            "primary_significant_fdr05": significant_primary,
            "minefield_focus": minefield_focus,
            "minefield_focus_significant": minefield_significant,
            "raven_covariate_sensitivity": raven,
            "raven_sensitivity_significant": significant_raven,
            "family_summary": family_summary,
        },
    )
    return {
        "primary": primary,
        "significant_primary": significant_primary,
        "minefield_focus": minefield_focus,
        "minefield_significant": minefield_significant,
        "raven": raven,
        "significant_raven": significant_raven,
        "family_summary": family_summary,
        "files": [path],
    }


def build_family_summary(
    primary: pd.DataFrame,
    raven: pd.DataFrame,
    minefield_focus: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    if not primary.empty:
        ok = primary.loc[primary["status"].eq("ok")]
        for keys, subset in ok.groupby(["questionnaire_family", "outcome_family", "domain"], dropna=False):
            rows.append(
                {
                    "analysis": "primary_age_adjusted",
                    "questionnaire_family": keys[0],
                    "outcome_family": keys[1],
                    "domain": keys[2],
                    "models_ok": len(subset),
                    "significant_fdr05": int(subset["significant_fdr05"].fillna(False).sum()),
                    "median_abs_beta": subset["beta_standardized"].abs().median(),
                }
            )
    if not minefield_focus.empty:
        for keys, subset in minefield_focus.groupby(["questionnaire_family", "outcome_family", "domain"], dropna=False):
            rows.append(
                {
                    "analysis": "minefield_focus_fdr",
                    "questionnaire_family": keys[0],
                    "outcome_family": keys[1],
                    "domain": keys[2],
                    "models_ok": len(subset),
                    "significant_fdr05": int(subset["significant_minefield_fdr05"].fillna(False).sum()),
                    "median_abs_beta": subset["beta_standardized"].abs().median(),
                }
            )
    if not raven.empty:
        ok = raven.loc[raven["status"].eq("ok")]
        for keys, subset in ok.groupby(["questionnaire_family", "outcome_family", "domain"], dropna=False):
            rows.append(
                {
                    "analysis": "raven_covariate_sensitivity",
                    "questionnaire_family": keys[0],
                    "outcome_family": keys[1],
                    "domain": keys[2],
                    "models_ok": len(subset),
                    "significant_fdr05": int(subset["significant_fdr05"].fillna(False).sum()),
                    "median_abs_beta": subset["beta_standardized"].abs().median(),
                }
            )
    return pd.DataFrame(rows)


def _format_p(value: float) -> str:
    if pd.isna(value):
        return ""
    if value < 0.001:
        return "< .001"
    return f"{value:.3f}"


def _format_num(value: float, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}"


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]], max_rows: int | None = None) -> str:
    if frame.empty:
        return "No FDR-significant results.\n"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [header, separator]
    for _, row in data.iterrows():
        values = []
        for column, _ in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                values.append(_format_num(value, 3))
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    if max_rows is not None and len(frame) > max_rows:
        rows.append("")
        rows.append(f"Table truncated to {max_rows} rows; see the CSV/XLSX output for all significant rows.")
    return "\n".join(rows) + "\n"


def prepare_correlation_table(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    result["spearman_rho_fmt"] = result["spearman_rho"].map(lambda x: _format_num(x, 2))
    result["spearman_q_fmt"] = result["spearman_q_fdr_bh"].map(_format_p)
    result["pearson_r_fmt"] = result["pearson_r"].map(lambda x: _format_num(x, 2))
    result["pearson_q_fmt"] = result["pearson_q_fdr_bh"].map(_format_p)
    return result


def prepare_regression_table(frame: pd.DataFrame, q_column: str = "q_fdr_bh") -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    result["beta_fmt"] = result["beta_standardized"].map(lambda x: _format_num(x, 2))
    result["ci_fmt"] = result.apply(
        lambda row: f"[{_format_num(row['ci_low'], 2)}, {_format_num(row['ci_high'], 2)}]",
        axis=1,
    )
    result["p_fmt"] = result["p_value"].map(_format_p)
    result["q_fmt"] = result[q_column].map(_format_p)
    result["r2_fmt"] = result["r_squared"].map(lambda x: _format_num(x, 2))
    return result


def write_paper_tables(
    correlations: dict,
    regressions: dict,
    dedicated: dict,
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
) -> list[Path]:
    out_dir = cfg.OUTPUT_ROOT / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    significant_corr = prepare_correlation_table(correlations["significant_any"])
    significant_reg = prepare_regression_table(regressions["significant_primary"])
    minefield_reg = prepare_regression_table(
        regressions["minefield_significant"],
        q_column="q_fdr_bh_minefield_focus",
    )
    raven_reg = prepare_regression_table(regressions["significant_raven"])

    table_map = {
        "significant_correlations_fdr.csv": significant_corr,
        "significant_primary_regressions_fdr.csv": significant_reg,
        "significant_minefield_focus_regressions_fdr.csv": minefield_reg,
        "significant_raven_sensitivity_regressions_fdr.csv": raven_reg,
        "family_summary.csv": regressions["family_summary"],
    }
    for filename, frame in table_map.items():
        path = out_dir / filename
        pd.DataFrame(frame).to_csv(path, index=False, encoding="utf-8-sig")
        files.append(path)

    summary_path = out_dir / "paper_results_summary.md"
    corr_columns = [
        ("questionnaire", "Questionnaire"),
        ("outcome", "PRE outcome"),
        ("outcome_family", "Family"),
        ("n", "n"),
        ("spearman_rho_fmt", "rho"),
        ("spearman_q_fmt", "Spearman q"),
        ("pearson_r_fmt", "r"),
        ("pearson_q_fmt", "Pearson q"),
    ]
    reg_columns = [
        ("questionnaire", "Questionnaire"),
        ("outcome", "PRE outcome"),
        ("outcome_family", "Family"),
        ("n", "n"),
        ("beta_fmt", "beta"),
        ("ci_fmt", "95% CI"),
        ("q_fmt", "FDR q"),
        ("r2_fmt", "R2"),
    ]
    lines = [
        "## Generated Results Tables",
        "",
        f"- Participants in baseline dataset: {len(dataset)}",
        f"- PRE outcomes available: {len(outcomes)}",
        f"- ABAS/BRIEF variables in dictionary: {len(questionnaires)}",
        f"- ABAS/BRIEF variables modelled with n >= {cfg.MIN_N}: {int(questionnaires['usable_for_models'].sum())}",
        f"- FDR-significant questionnaire-PRE correlations: {len(significant_corr)}",
        f"- FDR-significant primary age-adjusted regressions: {len(significant_reg)}",
        f"- FDR-significant Minefield-focus regressions: {len(minefield_reg)}",
        f"- FDR-significant Raven-covariate sensitivity regressions: {len(raven_reg)}",
        "",
        "### FDR-Significant ABAS/BRIEF Correlations With PRE Outcomes",
        "",
        markdown_table(significant_corr, corr_columns, max_rows=80),
        "",
        "### FDR-Significant Primary Age-Adjusted Regression Models",
        "",
        markdown_table(significant_reg, reg_columns, max_rows=80),
        "",
        "### FDR-Significant Minefield-Focus Regression Models",
        "",
        markdown_table(minefield_reg, reg_columns, max_rows=80),
        "",
        "### FDR-Significant Raven-Covariate Sensitivity Models",
        "",
        markdown_table(raven_reg, reg_columns, max_rows=80),
        "",
        dedicated["paper_markdown"].rstrip(),
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    files.append(summary_path)
    return files


def write_summary(
    elapsed_seconds: float,
    dataset: pd.DataFrame,
    outcomes: pd.DataFrame,
    questionnaires: pd.DataFrame,
    correlations: dict,
    regressions: dict,
    dedicated: dict,
) -> Path:
    valid_corr = correlations["all"].loc[correlations["all"]["status"].eq("ok")]
    primary_ok = regressions["primary"].loc[regressions["primary"]["status"].eq("ok")]
    raven_ok = regressions["raven"].loc[regressions["raven"]["status"].eq("ok")]
    dedicated_primary = dedicated["models"].loc[
        dedicated["models"]["sample_scope"].eq("primary_n99")
    ]
    lines = [
        "# ABAS/BRIEF Navigation PRE Analysis Summary",
        "",
        "## Input",
        "",
        f"- Database: `{analysis2_config.INPUT_DATABASE.relative_to(PROJECT_ROOT)}`",
        f"- SHA-256: `{file_sha256(analysis2_config.INPUT_DATABASE)}`",
        f"- Participants: {len(dataset)}",
        "- Scope: baseline PRE outcomes only; group and POST columns excluded.",
        "",
        "## Completed Analyses",
        "",
        f"- PRE outcomes in dictionary: {len(outcomes)}",
        f"- ABAS/BRIEF variables in dictionary: {len(questionnaires)}",
        f"- ABAS/BRIEF variables modelled with n >= {cfg.MIN_N}: {int(questionnaires['usable_for_models'].sum())}",
        f"- Correlation pairs tested: {len(valid_corr)}",
        f"- Correlations significant after FDR: {len(correlations['significant_any'])}",
        f"- Primary age-adjusted regressions tested: {len(primary_ok)}",
        f"- Primary regressions significant after FDR: {len(regressions['significant_primary'])}",
        f"- Minefield-focus regressions significant after within-focus FDR: {len(regressions['minefield_significant'])}",
        f"- Raven-covariate sensitivity regressions tested: {len(raven_ok)}",
        f"- Raven-covariate sensitivity regressions significant after FDR: {len(regressions['significant_raven'])}",
        f"- Dedicated curated non-Raven outcomes: {len(dedicated['outcomes'])}",
        f"- Dedicated primary screened sample: {int(dedicated['prepared']['included_primary_n99'].sum())}",
        f"- Dedicated primary model terms tested: {int(dedicated_primary['status'].eq('ok').sum())}",
        f"- Dedicated primary model terms significant after block-wise FDR: {int(dedicated_primary['significant_fdr05'].sum())}",
        "",
        "## Method Notes",
        "",
        "- Questionnaire-PRE associations were estimated with Pearson and Spearman correlations.",
        "- Primary models used standardized variables and HC3 robust standard errors.",
        f"- Primary model: `{cfg.PRIMARY_MODEL_LABEL}`.",
        "- Multiple testing was controlled with Benjamini-Hochberg FDR within each result family.",
        "- Dedicated total/subscale models exclude all Raven outcomes and compare identical complete-case samples with and without Raven PRE accuracy as a covariate.",
        "- Dedicated complete totals require all eight ABAS or all nine BRIEF standard scales; assumed/supplemental ABAS variables are excluded.",
        "- Minefield composites and log-transformed time outcomes were inherited from `analysis_2/common.py`.",
        "",
        "## Reproducibility",
        "",
        f"- Runtime: {elapsed_seconds:.1f} seconds",
        "- Run command: `python abas_brief_navigation_paper/analysis/run_analysis.py`",
        "- Detailed workbooks and paper-ready tables are under `abas_brief_navigation_paper/output/`.",
    ]
    path = cfg.OUTPUT_ROOT / "analysis_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_manifest(stage_rows: list[dict], elapsed_seconds: float) -> Path:
    generated = sorted(path for path in cfg.OUTPUT_ROOT.rglob("*") if path.is_file())
    files = pd.DataFrame(
        [
            {
                "path": str(path.relative_to(cfg.SUBPROJECT_ROOT)),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in generated
        ]
    )
    environment = pd.DataFrame(
        [
            {"item": "input_database", "value": str(analysis2_config.INPUT_DATABASE)},
            {"item": "input_sha256", "value": file_sha256(analysis2_config.INPUT_DATABASE)},
            {"item": "python", "value": sys.version},
            {"item": "platform", "value": platform.platform()},
            {"item": "pandas", "value": pd.__version__},
            {"item": "numpy", "value": np.__version__},
            {"item": "scipy", "value": scipy.__version__},
            {"item": "statsmodels", "value": statsmodels.__version__},
            {"item": "elapsed_seconds", "value": elapsed_seconds},
        ]
    )
    path = cfg.OUTPUT_ROOT / "run_manifest.xlsx"
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
    stages: list[dict] = []

    prepared, elapsed = run_stage("prepare_baseline_dataset", build_baseline_dataset)
    dataset, outcomes, questionnaires = prepared
    stages.append({"stage": "prepare_baseline_dataset", "status": "complete", "seconds": elapsed})

    _, elapsed = run_stage("write_dataset", write_dataset, dataset, outcomes, questionnaires)
    stages.append({"stage": "write_dataset", "status": "complete", "seconds": elapsed})

    descriptives, elapsed = run_stage("descriptives", run_descriptives, dataset, outcomes, questionnaires)
    stages.append({"stage": "descriptives", "status": "complete", "seconds": elapsed})

    correlations, elapsed = run_stage("correlations", run_correlations, dataset, outcomes, questionnaires)
    stages.append({"stage": "correlations", "status": "complete", "seconds": elapsed})

    regressions, elapsed = run_stage("regressions", run_regressions, dataset, outcomes, questionnaires)
    stages.append({"stage": "regressions", "status": "complete", "seconds": elapsed})

    dedicated, elapsed = run_stage("dedicated_totals_subscales", dedicated_models.run, dataset)
    stages.append({"stage": "dedicated_totals_subscales", "status": "complete", "seconds": elapsed})

    _, elapsed = run_stage(
        "paper_tables",
        write_paper_tables,
        correlations,
        regressions,
        dedicated,
        dataset,
        outcomes,
        questionnaires,
    )
    stages.append({"stage": "paper_tables", "status": "complete", "seconds": elapsed})

    total_elapsed = time.perf_counter() - started
    summary_path = write_summary(
        total_elapsed,
        dataset,
        outcomes,
        questionnaires,
        correlations,
        regressions,
        dedicated,
    )
    manifest_path = write_manifest(stages, total_elapsed)
    print(f"ABAS/BRIEF navigation PRE analysis complete in {total_elapsed:.1f}s", flush=True)
    print(f"Summary: {summary_path}", flush=True)
    print(f"Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()

