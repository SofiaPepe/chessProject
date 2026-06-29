from __future__ import annotations

import math
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from common import fdr_bh, to_numeric, write_workbook
from config import ALPHA, GROUP_COLUMN, ID_COLUMN, OUTPUT_ROOT, PCA_DOMAINS


OUT_DIR = OUTPUT_ROOT / "07_pca"


def pooled_domain_data(df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, list[str]]:
    existing = [
        feature
        for feature in features
        if f"{feature}_PRE" in df and f"{feature}_POST" in df
    ]
    rows = []
    for _, record in df.iterrows():
        for occasion in ["PRE", "POST"]:
            row = {
                ID_COLUMN: record[ID_COLUMN],
                GROUP_COLUMN: record[GROUP_COLUMN],
                "time": occasion,
            }
            for feature in existing:
                row[feature] = record[f"{feature}_{occasion}"]
            rows.append(row)
    pooled = pd.DataFrame(rows)
    for feature in existing:
        pooled[feature] = to_numeric(pooled[feature])
    minimum_observed = max(2, math.ceil(len(existing) * 0.60))
    pooled["observed_features"] = pooled[existing].notna().sum(axis=1)
    pooled = pooled[pooled["observed_features"] >= minimum_observed].copy()
    return pooled, existing


def domain_pca(df: pd.DataFrame, domain: str, features: list[str]) -> dict:
    pooled, existing = pooled_domain_data(df, features)
    if len(existing) < 2 or len(pooled) < 10:
        return {"status": "insufficient_data", "domain": domain}

    medians = pooled[existing].median()
    imputed = pooled[existing].fillna(medians)
    means = imputed.mean(axis=0)
    scales = imputed.std(axis=0, ddof=0).replace(0, 1)
    standardized = ((imputed - means) / scales).to_numpy()
    u, singular_values, components = np.linalg.svd(standardized, full_matrices=False)
    transformed = u * singular_values
    explained_variance = (singular_values ** 2) / (len(imputed) - 1)
    explained_ratio = explained_variance / explained_variance.sum()
    component_names = [f"PC{index + 1}" for index in range(len(existing))]

    scores = pooled[[ID_COLUMN, GROUP_COLUMN, "time", "observed_features"]].reset_index(drop=True)
    for index, component in enumerate(component_names):
        scores[component] = transformed[:, index]
    loadings = pd.DataFrame(
        components.T,
        index=existing,
        columns=component_names,
    ).reset_index(names="feature")
    explained = pd.DataFrame(
        {
            "component": component_names,
            "eigenvalue": explained_variance,
            "explained_variance_ratio": explained_ratio,
            "cumulative_variance_ratio": np.cumsum(explained_ratio),
        }
    )
    retained_n = max(1, int((explained_variance > 1).sum()))
    explained["retained_eigenvalue_gt_1"] = [index < retained_n for index in range(len(explained))]
    imputation = pd.DataFrame(
        {
            "feature": existing,
            "median_used": [medians[feature] for feature in existing],
            "n_missing_imputed": [int(pooled[feature].isna().sum()) for feature in existing],
            "standardization_mean": means.to_numpy(),
            "standardization_scale": scales.to_numpy(),
        }
    )

    tests = []
    for component in component_names[:retained_n]:
        component_data = scores[[ID_COLUMN, GROUP_COLUMN, "time", component]].dropna()
        wide = component_data.pivot(index=[ID_COLUMN, GROUP_COLUMN], columns="time", values=component).reset_index()
        wide = wide.dropna(subset=["PRE", "POST"])
        if wide[GROUP_COLUMN].nunique() < 2 or wide[ID_COLUMN].nunique() < 6:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                wide["change"] = wide["POST"] - wide["PRE"]
                wide["group_experimental"] = (to_numeric(wide[GROUP_COLUMN]) == 1).astype(float)
                fit = smf.ols("change ~ group_experimental", data=wide).fit(cov_type="HC3")
            beta = fit.params["group_experimental"]
            se = fit.bse["group_experimental"]
            t_value = beta / se if se else np.nan
            tests.append(
                {
                    "domain": domain,
                    "component": component,
                    "n_ids": wide[ID_COLUMN].nunique(),
                    "interaction_beta": beta,
                    "interaction_p": fit.pvalues["group_experimental"],
                    "interaction_np2": (t_value ** 2) / (t_value ** 2 + fit.df_resid) if pd.notna(t_value) else np.nan,
                }
            )
        except Exception as exc:
            tests.append({"domain": domain, "component": component, "status": f"{type(exc).__name__}: {exc}"})

    domain_dir = OUT_DIR / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    scree_path = domain_dir / "scree_plot.png"
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.plot(range(1, len(explained) + 1), explained["eigenvalue"], marker="o")
    ax.axhline(1, linestyle="--", color="#777777", linewidth=1)
    ax.set_xlabel("Component")
    ax.set_ylabel("Eigenvalue")
    ax.set_title(f"{domain}: PCA scree plot")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(scree_path, dpi=220)
    plt.close(fig)

    pc1_path = domain_dir / "pc1_prepost_by_group.png"
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    summary = scores.groupby([GROUP_COLUMN, "time"])["PC1"].agg(["count", "mean", "std"]).reset_index()
    summary["ci"] = 1.96 * summary["std"] / np.sqrt(summary["count"])
    for code, label, color in [(1, "experimental", "#3566A5"), (2, "control", "#C45A11")]:
        group = summary[summary[GROUP_COLUMN] == code].copy()
        group["x"] = group["time"].map({"PRE": 0, "POST": 1})
        group = group.sort_values("x")
        ax.errorbar(group["x"], group["mean"], yerr=group["ci"], marker="o", linewidth=2, capsize=4, label=label, color=color)
    ax.set_xticks([0, 1], ["PRE", "POST"])
    ax.set_ylabel("PC1 score")
    ax.set_title(f"{domain}: PC1")
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(pc1_path, dpi=220)
    plt.close(fig)
    return {
        "status": "ok",
        "domain": domain,
        "scores": scores,
        "loadings": loadings,
        "explained": explained,
        "imputation": imputation,
        "tests": pd.DataFrame(tests),
        "files": [scree_path, pc1_path],
    }


def run(df: pd.DataFrame) -> dict:
    results = [domain_pca(df, domain, features) for domain, features in PCA_DOMAINS.items()]
    sheets = {}
    all_tests = []
    files = []
    for result in results:
        domain = result["domain"]
        if result["status"] != "ok":
            continue
        sheets[f"{domain}_explained"] = result["explained"]
        sheets[f"{domain}_loadings"] = result["loadings"]
        sheets[f"{domain}_scores"] = result["scores"]
        sheets[f"{domain}_imputation"] = result["imputation"]
        all_tests.append(result["tests"])
        files.extend(result["files"])
    tests = pd.concat(all_tests, ignore_index=True) if all_tests else pd.DataFrame()
    tests = fdr_bh(tests, "interaction_p") if not tests.empty else tests
    if not tests.empty:
        tests["significant_p05"] = tests["interaction_p"] < ALPHA
        tests["significant_fdr05"] = tests["q_fdr_bh"] < ALPHA
    sheets["pc_group_x_time"] = tests
    sheets["domain_status"] = pd.DataFrame([{key: value for key, value in result.items() if key in {"domain", "status"}} for result in results])
    path = OUT_DIR / "pca_results.xlsx"
    write_workbook(path, sheets)
    return {"domains": results, "tests": tests, "files": [path, *files]}
