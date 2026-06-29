from __future__ import annotations

import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from common import fdr_bh, hedges_g, safe_filename, to_numeric, write_workbook
from config import ALPHA, EFFECTIVENESS_SPECS, GROUP_COLUMN, GROUP_LABELS, ID_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "05_effectiveness"
PLOT_DIR = OUT_DIR / "plots"


def individual_effectiveness(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variable, minimum, maximum in EFFECTIVENESS_SPECS:
        pre_col = f"{variable}_PRE"
        post_col = f"{variable}_POST"
        if pre_col not in df or post_col not in df:
            continue
        for _, record in df.iterrows():
            pre = pd.to_numeric(pd.Series([record[pre_col]]), errors="coerce").iloc[0]
            post = pd.to_numeric(pd.Series([record[post_col]]), errors="coerce").iloc[0]
            status = "ok"
            value = np.nan
            if pd.isna(pre) or pd.isna(post):
                status = "missing_pre_or_post"
            elif not minimum <= pre <= maximum or not minimum <= post <= maximum:
                status = "outside_confirmed_bounds"
            elif pre == maximum:
                status = "ceiling_no_room_to_improve"
            else:
                value = ((post - pre) / (maximum - pre)) * 100
            rows.append(
                {
                    ID_COLUMN: record[ID_COLUMN],
                    GROUP_COLUMN: record[GROUP_COLUMN],
                    "group_label": record.get("group_label"),
                    "age": record.get("age"),
                    "sex": record.get("sex"),
                    "class": record.get("class"),
                    "variable": variable,
                    "pre_col": pre_col,
                    "post_col": post_col,
                    "minimum": minimum,
                    "maximum": maximum,
                    "pre": pre,
                    "post": post,
                    "effectiveness_pct": value,
                    "status": status,
                }
            )
    return pd.DataFrame(rows)


def adjusted_group_model(data: pd.DataFrame, variable: str) -> dict:
    model = data.copy()
    model["effectiveness_pct"] = to_numeric(model["effectiveness_pct"])
    model["group_experimental"] = (to_numeric(model[GROUP_COLUMN]) == 1).astype(float)
    model["age"] = to_numeric(model["age"])
    for column in ["sex", "class"]:
        model[column] = model[column].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
    model["class_cov"] = model["class"]
    model = model.dropna(subset=["effectiveness_pct", "group_experimental", "age", "sex", "class_cov"])
    base = {"variable": variable, "n": len(model)}
    if len(model) < 20 or model["group_experimental"].nunique() < 2:
        return {**base, "status": "insufficient_data"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = smf.ols("effectiveness_pct ~ group_experimental + age + C(sex) + C(class_cov)", data=model).fit(cov_type="HC3")
        ci = fit.conf_int().loc["group_experimental"]
        return {
            **base,
            "status": "ok",
            "group_beta": fit.params["group_experimental"],
            "group_se": fit.bse["group_experimental"],
            "group_ci_low": ci.iloc[0],
            "group_ci_high": ci.iloc[1],
            "group_p": fit.pvalues["group_experimental"],
            "r_squared": fit.rsquared,
        }
    except Exception as exc:
        return {**base, "status": f"{type(exc).__name__}: {exc}"}


def plot_effectiveness(data: pd.DataFrame, variable: str, path) -> bool:
    plot_data = data.dropna(subset=["effectiveness_pct", "group_label"])
    if plot_data.empty:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    groups = [
        plot_data.loc[plot_data["group_label"] == label, "effectiveness_pct"].to_numpy()
        for label in ["experimental", "control"]
    ]
    if any(len(values) == 0 for values in groups):
        plt.close(fig)
        return False
    box = ax.boxplot(groups, labels=["experimental", "control"], patch_artist=True, showfliers=False)
    for patch, color in zip(box["boxes"], ["#3566A5", "#C45A11"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.55)
    rng = np.random.default_rng(20260629)
    for x, values in enumerate(groups, 1):
        ax.scatter(rng.normal(x, 0.04, len(values)), values, s=16, alpha=0.55, color="#222222")
    ax.axhline(0, color="#777777", linewidth=1, linestyle="--")
    ax.set_ylabel("Effectiveness (%)")
    ax.set_title(variable)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return True


def run(df: pd.DataFrame) -> dict:
    individual = individual_effectiveness(df)
    comparison_rows = []
    summary_rows = []
    adjusted_rows = []
    status = individual.groupby(["variable", "status"], dropna=False).size().reset_index(name="n")
    plot_rows = []
    for variable, subset in individual.groupby("variable"):
        valid = subset[subset["status"] == "ok"].copy()
        for code, label in GROUP_LABELS.items():
            values = valid.loc[valid[GROUP_COLUMN] == code, "effectiveness_pct"].dropna()
            summary_rows.append(
                {
                    "variable": variable,
                    "group": label,
                    "n": len(values),
                    "mean": values.mean(),
                    "sd": values.std(ddof=1),
                    "median": values.median(),
                    "q1": values.quantile(0.25),
                    "q3": values.quantile(0.75),
                }
            )
        experimental = valid.loc[valid[GROUP_COLUMN] == 1, "effectiveness_pct"]
        control = valid.loc[valid[GROUP_COLUMN] == 2, "effectiveness_pct"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            welch_p = stats.ttest_ind(experimental, control, equal_var=False).pvalue if len(experimental) >= 2 and len(control) >= 2 else np.nan
            try:
                mann_p = stats.mannwhitneyu(experimental, control, alternative="two-sided").pvalue
            except ValueError:
                mann_p = np.nan
        comparison_rows.append(
            {
                "variable": variable,
                "n_experimental": len(experimental),
                "n_control": len(control),
                "experimental_mean": experimental.mean(),
                "control_mean": control.mean(),
                "mean_difference": experimental.mean() - control.mean(),
                "hedges_g": hedges_g(experimental, control),
                "welch_p": welch_p,
                "mann_whitney_p": mann_p,
            }
        )
        adjusted_rows.append(adjusted_group_model(valid, variable))
        plot_path = PLOT_DIR / f"{safe_filename(variable)}_effectiveness.png"
        plot_rows.append({"variable": variable, "path": str(plot_path), "created": plot_effectiveness(valid, variable, plot_path)})

    comparison = fdr_bh(pd.DataFrame(comparison_rows), "welch_p")
    if not comparison.empty:
        comparison["significant_p05"] = comparison["welch_p"] < ALPHA
        comparison["significant_fdr05"] = comparison["q_fdr_bh"] < ALPHA
        comparison = comparison.sort_values(["significant_fdr05", "welch_p"], ascending=[False, True])
    adjusted = fdr_bh(pd.DataFrame(adjusted_rows), "group_p")
    if not adjusted.empty:
        adjusted["significant_p05"] = adjusted["group_p"] < ALPHA
        adjusted["significant_fdr05"] = adjusted["q_fdr_bh"] < ALPHA
    path = OUT_DIR / "treatment_effectiveness.xlsx"
    write_workbook(
        path,
        {
            "individual": individual,
            "status_counts": status,
            "group_summary": pd.DataFrame(summary_rows),
            "group_comparison": comparison,
            "age_adjusted_group": adjusted,
            "plot_manifest": pd.DataFrame(plot_rows),
            "specifications": pd.DataFrame(EFFECTIVENESS_SPECS, columns=["variable", "minimum", "maximum"]),
        },
    )
    return {
        "individual": individual,
        "comparison": comparison,
        "adjusted": adjusted,
        "files": [path, *[row["path"] for row in plot_rows if row["created"]]],
    }
