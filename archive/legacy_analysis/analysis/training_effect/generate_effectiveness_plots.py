from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
EFFECTIVENESS_XLSX = ROOT / "output" / "training_effect" / "treatment_effectiveness" / "treatment_effectiveness_results.xlsx"
OUT_DIR = ROOT / "output" / "training_effect" / "treatment_effectiveness" / "plots"
GROUP_DIR = OUT_DIR / "group_comparisons"
SUMMARY_DIR = OUT_DIR / "summary"
AGE_ADJUSTED_DIR = OUT_DIR / "age_adjusted"
MANIFEST_XLSX = OUT_DIR / "effectiveness_plot_manifest.xlsx"

GROUP_COLORS = {
    "experimental": "#3566A5",
    "control": "#C45A11",
}


def safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe or "plot"


def format_p(value) -> str:
    if pd.isna(value):
        return "p = NA"
    if value < 0.001:
        return "p < .001"
    return f"p = {value:.3f}"


def read_effectiveness() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    individual = pd.read_excel(EFFECTIVENESS_XLSX, sheet_name="individual_effectiveness")
    summary = pd.read_excel(EFFECTIVENESS_XLSX, sheet_name="group_summary")
    comparison = pd.read_excel(EFFECTIVENESS_XLSX, sheet_name="group_comparison")
    age_adjusted = pd.read_excel(EFFECTIVENESS_XLSX, sheet_name="age_adjusted_group")
    individual = individual[individual["effectiveness_status"].eq("ok")].copy()
    return individual, summary, comparison, age_adjusted


def plot_group_comparison(individual: pd.DataFrame, comparison: pd.DataFrame, variable: str, path: Path) -> dict:
    data = individual[individual["variable"].eq(variable)].copy()
    comp_row = comparison[comparison["variable"].eq(variable)]
    p_value = comp_row["welch_p"].iloc[0] if not comp_row.empty and "welch_p" in comp_row else np.nan
    q_value = comp_row["welch_q_fdr_bh"].iloc[0] if not comp_row.empty and "welch_q_fdr_bh" in comp_row else np.nan

    fig, ax = plt.subplots(figsize=(7.5, 5))
    groups = ["experimental", "control"]
    positions = np.arange(len(groups))
    means = []
    errors = []

    for idx, group in enumerate(groups):
        values = data.loc[data["group_label"].eq(group), "effectiveness_pct"].dropna()
        means.append(values.mean())
        se = values.std(ddof=1) / np.sqrt(values.count()) if values.count() > 1 else np.nan
        errors.append(1.96 * se if pd.notna(se) else 0)
        jitter = np.random.default_rng(42 + idx).normal(0, 0.035, size=len(values))
        ax.scatter(
            np.full(len(values), positions[idx]) + jitter,
            values,
            s=22,
            alpha=0.42,
            color=GROUP_COLORS[group],
            edgecolor="none",
        )

    ax.bar(
        positions,
        means,
        yerr=errors,
        capsize=5,
        color=[GROUP_COLORS[group] for group in groups],
        alpha=0.45,
        edgecolor="#222222",
        linewidth=1,
    )
    ax.axhline(0, color="#555555", linewidth=0.9)
    ax.set_xticks(positions)
    ax.set_xticklabels(["Experimental", "Control"])
    ax.set_ylabel("Effectiveness (%)")
    ax.set_title(f"{variable}: treatment effectiveness by group")
    ax.text(
        0.98,
        0.98,
        f"Welch {format_p(p_value)}\nFDR q = {q_value:.3f}" if pd.notna(q_value) else f"Welch {format_p(p_value)}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
    )
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return {"variable": variable, "plot_type": "group_comparison", "plot_path": str(path), "p_value": p_value, "q_fdr": q_value}


def plot_difference_summary(comparison: pd.DataFrame, path: Path) -> dict:
    data = comparison.sort_values("mean_difference_exp_minus_control").copy()
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    colors = np.where(data["significant_p05"].fillna(False), "#3566A5", "#888888")
    ax.barh(data["variable"], data["mean_difference_exp_minus_control"], color=colors, alpha=0.78)
    ax.axvline(0, color="#222222", linewidth=0.9)
    ax.set_xlabel("Mean effectiveness difference: experimental - control")
    ax.set_title("Treatment effectiveness group differences")
    ax.grid(axis="x", alpha=0.22)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return {"variable": "all", "plot_type": "group_difference_summary", "plot_path": str(path)}


def plot_age_adjusted_summary(age_adjusted: pd.DataFrame, path: Path) -> dict:
    data = age_adjusted[age_adjusted["status"].eq("ok")].copy()
    data = data.sort_values("group_effect_exp_minus_control_age_adjusted")
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    colors = np.where(data["significant_age_adjusted_p05"].fillna(False), "#3566A5", "#888888")
    ax.barh(data["variable"], data["group_effect_exp_minus_control_age_adjusted"], color=colors, alpha=0.78)
    ax.axvline(0, color="#222222", linewidth=0.9)
    ax.set_xlabel("Age-adjusted group effect: experimental - control")
    ax.set_title("Treatment effectiveness group differences adjusted for age")
    ax.grid(axis="x", alpha=0.22)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return {"variable": "all", "plot_type": "age_adjusted_group_summary", "plot_path": str(path)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    individual, _, comparison, age_adjusted = read_effectiveness()
    manifest = []

    manifest.append(plot_difference_summary(comparison, SUMMARY_DIR / "effectiveness_group_difference_summary.png"))
    manifest.append(
        plot_age_adjusted_summary(
            age_adjusted,
            AGE_ADJUSTED_DIR / "effectiveness_group_difference_age_adjusted_summary.png",
        )
    )
    for variable in comparison["variable"].dropna():
        manifest.append(
            plot_group_comparison(
                individual,
                comparison,
                variable,
                GROUP_DIR / f"{safe_filename(variable)}_effectiveness_by_group.png",
            )
        )

    manifest_df = pd.DataFrame(manifest)
    with pd.ExcelWriter(MANIFEST_XLSX, engine="openpyxl") as writer:
        manifest_df.to_excel(writer, sheet_name="plots", index=False)

    print("Effectiveness plots complete")
    print(f"Group plots: {GROUP_DIR}")
    print(f"Summary plots: {SUMMARY_DIR}")
    print(f"Age-adjusted plots: {AGE_ADJUSTED_DIR}")
    print(f"Manifest: {MANIFEST_XLSX}")


if __name__ == "__main__":
    main()
