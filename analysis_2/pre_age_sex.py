from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from common import build_analysis_dataset, fdr_bh, find_prepost_pairs, hedges_g, to_numeric, write_workbook
from config import ALPHA, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "02_baseline"
OUT_PATH = OUT_DIR / "pre_measures_age_sex.xlsx"
SUMMARY_PATH = OUT_DIR / "pre_measures_age_sex_summary.md"


def baseline_measure_specs(df: pd.DataFrame) -> list[dict]:
    specs = [
        {
            **pair,
            "measure_family": "cognitive_pre",
        }
        for pair in find_prepost_pairs(df)
    ]
    for column in sorted(
        column for column in df.columns if str(column).startswith(("ABAS_", "BRIEF_"))
    ):
        values = to_numeric(df[column])
        if values.notna().sum() < 20 or values.nunique(dropna=True) < 2:
            continue
        specs.append(
            {
                "variable": str(column),
                "pre_col": column,
                "post_col": "",
                "domain": "questionnaire",
                "transformation": "raw",
                "measure_family": "ABAS_BRIEF_baseline",
            }
        )
    return specs


def _welch_ttest(first: pd.Series, second: pd.Series) -> tuple[float, float]:
    first = to_numeric(first).dropna()
    second = to_numeric(second).dropna()
    if len(first) < 2 or len(second) < 2:
        return np.nan, np.nan
    result = stats.ttest_ind(first, second, equal_var=False, nan_policy="omit")
    return float(result.statistic), float(result.pvalue)


def _clean_pre_data(df: pd.DataFrame, pre_col: str) -> pd.DataFrame:
    data = df[[pre_col, "age", "sex"]].copy()
    data["outcome"] = to_numeric(data[pre_col])
    data["age"] = to_numeric(data["age"])
    data["sex"] = data["sex"].astype(str).str.strip().str.upper()
    data = data.dropna(subset=["outcome", "age", "sex"])
    return data.loc[data["sex"].isin(["F", "M"]) & data["age"].isin([5, 6, 7])].copy()


def _descriptives(data: pd.DataFrame, pair: dict) -> tuple[list[dict], list[dict]]:
    age_rows = []
    for age, subset in data.groupby("age"):
        age_rows.append(
            {
                "variable": pair["variable"],
                "age": int(age),
                "n": len(subset),
                "mean": subset["outcome"].mean(),
                "sd": subset["outcome"].std(ddof=1),
                "median": subset["outcome"].median(),
            }
        )

    sex_rows = []
    for sex, subset in data.groupby("sex"):
        sex_rows.append(
            {
                "variable": pair["variable"],
                "sex": sex,
                "n": len(subset),
                "mean": subset["outcome"].mean(),
                "sd": subset["outcome"].std(ddof=1),
                "median": subset["outcome"].median(),
            }
        )
    return age_rows, sex_rows


def _test_pre_measure(df: pd.DataFrame, pair: dict) -> tuple[dict, list[dict], dict, list[dict], list[dict]]:
    data = _clean_pre_data(df, pair["pre_col"])
    age_rows, sex_rows = _descriptives(data, pair)

    base = {
        **pair,
        "n": len(data),
        "n_age_5": int((data["age"] == 5).sum()),
        "n_age_6": int((data["age"] == 6).sum()),
        "n_age_7": int((data["age"] == 7).sum()),
        "n_female": int((data["sex"] == "F").sum()),
        "n_male": int((data["sex"] == "M").sum()),
        "test_family": "Welch independent-samples t-tests on baseline/PRE scores",
    }
    if len(data) < 20 or data["age"].nunique() < 2 or data["sex"].nunique() < 2:
        summary = {**base, "status": "insufficient_data"}
        sex_test = {**base, "status": "insufficient_data"}
        return summary, [], sex_test, age_rows, sex_rows

    female = data.loc[data["sex"] == "F", "outcome"]
    male = data.loc[data["sex"] == "M", "outcome"]
    sex_t, sex_p = _welch_ttest(male, female)
    sex_test = {
        **base,
        "status": "ok",
        "comparison": "M-F",
        "female_mean": female.mean(),
        "male_mean": male.mean(),
        "mean_difference_male_minus_female": male.mean() - female.mean(),
        "sex_t": sex_t,
        "sex_p": sex_p,
        "sex_hedges_g_male_minus_female": hedges_g(male, female),
    }

    age_tests = []
    for younger, older in [(5, 6), (5, 7), (6, 7)]:
        younger_values = data.loc[data["age"] == younger, "outcome"]
        older_values = data.loc[data["age"] == older, "outcome"]
        age_t, age_p = _welch_ttest(older_values, younger_values)
        age_tests.append(
            {
                **base,
                "status": "ok",
                "comparison": f"{older}-{younger}",
                "younger_age": younger,
                "older_age": older,
                "younger_n": len(younger_values),
                "older_n": len(older_values),
                "younger_mean": younger_values.mean(),
                "older_mean": older_values.mean(),
                "mean_difference_older_minus_younger": older_values.mean() - younger_values.mean(),
                "age_pair_t": age_t,
                "age_pair_p": age_p,
                "age_pair_hedges_g_older_minus_younger": hedges_g(older_values, younger_values),
            }
        )

    summary = {
        **base,
        "status": "ok",
        "sex_p": sex_p,
        "age_min_pairwise_p": min(
            [row["age_pair_p"] for row in age_tests if pd.notna(row["age_pair_p"])],
            default=np.nan,
        ),
    }
    return summary, age_tests, sex_test, age_rows, sex_rows


def _summarize_tests(summary: pd.DataFrame, age_tests: pd.DataFrame, sex_tests: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()

    if not sex_tests.empty:
        sex_lookup = sex_tests.set_index("variable")
        result["sex_q_fdr_bh"] = result["variable"].map(sex_lookup["sex_q_fdr_bh"])
        result["sex_significant_p05"] = result["sex_p"] < ALPHA
        result["sex_significant_fdr05"] = result["sex_q_fdr_bh"] < ALPHA
    else:
        result["sex_q_fdr_bh"] = np.nan
        result["sex_significant_p05"] = False
        result["sex_significant_fdr05"] = False

    if not age_tests.empty:
        grouped = age_tests.groupby("variable", dropna=False)
        result["age_min_pairwise_q_fdr_bh"] = result["variable"].map(grouped["age_pair_q_fdr_bh"].min())
        result["age_significant_p05"] = result["variable"].map(grouped["age_pair_p"].min()) < ALPHA
        age_pairs = pd.Series(
            {
                variable: ", ".join(
                    frame.loc[frame["age_pair_significant_fdr05"], "comparison"].astype(str).tolist()
                )
                for variable, frame in grouped
            }
        )
        result["age_significant_pairs_fdr05"] = result["variable"].map(age_pairs).fillna("")
        result["age_significant_fdr05"] = result["age_significant_pairs_fdr05"].str.len() > 0
    else:
        result["age_min_pairwise_q_fdr_bh"] = np.nan
        result["age_significant_p05"] = False
        result["age_significant_pairs_fdr05"] = ""
        result["age_significant_fdr05"] = False

    return result.sort_values(["age_significant_fdr05", "sex_significant_fdr05", "variable"], ascending=[False, False, True])


def _write_summary(summary: pd.DataFrame, age_tests: pd.DataFrame, sex_tests: pd.DataFrame) -> None:
    valid = summary.loc[summary["status"].eq("ok")].copy()
    age_fdr = valid.loc[valid["age_significant_fdr05"], "variable"].tolist()
    sex_fdr = valid.loc[valid["sex_significant_fdr05"], "variable"].tolist()
    age_nominal = valid.loc[valid["age_significant_p05"], "variable"].tolist()
    sex_nominal = valid.loc[valid["sex_significant_p05"], "variable"].tolist()
    significant_age_tests = age_tests.loc[age_tests.get("age_pair_significant_fdr05", False).fillna(False)]
    significant_sex_tests = sex_tests.loc[sex_tests.get("sex_significant_fdr05", False).fillna(False)]
    lines = [
        "# PRE measures: age and sex t-tests",
        "",
        f"- Baseline/PRE measures tested: {len(valid)}",
        "- Sex check: Welch independent-samples t-tests comparing males and females on each baseline/PRE measure.",
        "- Age check: pairwise Welch independent-samples t-tests comparing ages 5 vs 6, 5 vs 7, and 6 vs 7 on each baseline/PRE measure.",
        "- Sex and age p-values were corrected separately using Benjamini-Hochberg FDR.",
        f"- Age outcomes with nominal p < .05 in at least one pairwise comparison: {len(age_nominal)} ({', '.join(age_nominal) or 'none'}).",
        f"- Age outcomes significant after FDR in at least one pairwise comparison: {len(age_fdr)} ({', '.join(age_fdr) or 'none'}).",
        f"- Sex outcomes with nominal p < .05: {len(sex_nominal)} ({', '.join(sex_nominal) or 'none'}).",
        f"- Sex outcomes significant after FDR: {len(sex_fdr)} ({', '.join(sex_fdr) or 'none'}).",
        f"- Significant age pairwise tests after FDR: {len(significant_age_tests)}.",
        f"- Significant sex tests after FDR: {len(significant_sex_tests)}.",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(df: pd.DataFrame) -> dict:
    summary_rows = []
    age_test_rows = []
    sex_test_rows = []
    age_descriptives = []
    sex_descriptives = []

    for pair in baseline_measure_specs(df):
        summary, age_tests, sex_test, age_rows, sex_rows = _test_pre_measure(df, pair)
        summary_rows.append(summary)
        age_test_rows.extend(age_tests)
        sex_test_rows.append(sex_test)
        age_descriptives.extend(age_rows)
        sex_descriptives.extend(sex_rows)

    age_tests = fdr_bh(pd.DataFrame(age_test_rows), "age_pair_p", "age_pair_q_fdr_bh")
    if not age_tests.empty:
        age_tests["age_pair_significant_p05"] = age_tests["age_pair_p"] < ALPHA
        age_tests["age_pair_significant_fdr05"] = age_tests["age_pair_q_fdr_bh"] < ALPHA
        age_tests = age_tests.sort_values(["age_pair_significant_fdr05", "age_pair_p"], ascending=[False, True])

    sex_tests = fdr_bh(pd.DataFrame(sex_test_rows), "sex_p", "sex_q_fdr_bh")
    if not sex_tests.empty:
        sex_tests["sex_significant_p05"] = sex_tests["sex_p"] < ALPHA
        sex_tests["sex_significant_fdr05"] = sex_tests["sex_q_fdr_bh"] < ALPHA
        sex_tests = sex_tests.sort_values(["sex_significant_fdr05", "sex_p"], ascending=[False, True])

    summary = _summarize_tests(pd.DataFrame(summary_rows), age_tests, sex_tests)

    metadata = pd.DataFrame(
        [
            {"item": "scope", "value": "PRE cognitive measures plus baseline ABAS/BRIEF questionnaire measures"},
            {"item": "sex_test", "value": "Welch independent-samples t-test: male vs female"},
            {"item": "age_test", "value": "Pairwise Welch independent-samples t-tests: 5 vs 6, 5 vs 7, 6 vs 7"},
            {"item": "multiplicity", "value": "Benjamini-Hochberg FDR separately for sex tests and age pairwise tests"},
        ]
    )
    write_workbook(
        OUT_PATH,
        {
            "metadata": metadata,
            "adjusted_tests": summary,
            "age_pairwise_t_tests": age_tests,
            "sex_t_tests": sex_tests,
            "age_descriptives": pd.DataFrame(age_descriptives),
            "sex_descriptives": pd.DataFrame(sex_descriptives),
        },
    )
    _write_summary(summary, age_tests, sex_tests)
    return {
        "tests": summary,
        "age_pairwise": age_tests,
        "sex_tests": sex_tests,
        "age_descriptives": age_descriptives,
        "sex_descriptives": sex_descriptives,
    }


def main() -> None:
    result = run(build_analysis_dataset())
    valid = result["tests"].loc[result["tests"]["status"].eq("ok")]
    print(f"PRE measures tested: {len(valid)}")
    print(f"Age outcomes significant after FDR: {int(valid['age_significant_fdr05'].sum())}")
    print(f"Sex outcomes significant after FDR: {int(valid['sex_significant_fdr05'].sum())}")
    print(f"Workbook: {OUT_PATH}")
    print(f"Summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
