from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import config as cfg


def main() -> None:
    quarto = shutil.which("quarto")
    if quarto is None:
        raise RuntimeError("Quarto is not installed or not available on PATH")
    source = cfg.PAPER_ROOT / "abasbrief_paper.qmd"
    if not source.exists():
        raise FileNotFoundError(f"Paper source not found: {source}")
    required = [
        cfg.OUTPUT_ROOT / "analysis_results.xlsx",
        cfg.TABLE_ROOT / "results_narrative.md",
        cfg.FIGURE_ROOT / "primary_forest_plot.png",
        cfg.FIGURE_ROOT / "significant_beta_heatmap.png",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Analysis outputs are missing; run run_analysis.py first: "
            + ", ".join(str(path) for path in missing)
        )
    # Use a temporary Quarto/Deno cache inside the output tree. This makes
    # rendering work in restricted environments without leaving cache files in
    # the reproducible deliverables.
    with tempfile.TemporaryDirectory(
        prefix=".quarto_render_", dir=cfg.OUTPUT_ROOT
    ) as cache_directory:
        cache_root = Path(cache_directory)
        local_app_data = cache_root / "local"
        roaming_app_data = cache_root / "roaming"
        deno_dir = cache_root / "deno"
        for path in (local_app_data, roaming_app_data, deno_dir):
            path.mkdir(parents=True, exist_ok=True)
        render_env = os.environ.copy()
        render_env["LOCALAPPDATA"] = str(local_app_data)
        render_env["APPDATA"] = str(roaming_app_data)
        render_env["DENO_DIR"] = str(deno_dir)
        completed = subprocess.run(
            [quarto, "render", str(source)],
            cwd=cfg.PROJECT_ROOT,
            env=render_env,
            check=False,
            text=True,
        )
    if completed.returncode != 0:
        sys.exit(completed.returncode)
    expected = [
        cfg.PAPER_ROOT / "abasbrief_paper.html",
        cfg.PAPER_ROOT / "abasbrief_paper.docx",
    ]
    missing_rendered = [path for path in expected if not path.exists()]
    if missing_rendered:
        raise RuntimeError(f"Expected rendered files missing: {missing_rendered}")
    for path in expected:
        print(f"Rendered: {path}")


if __name__ == "__main__":
    main()
