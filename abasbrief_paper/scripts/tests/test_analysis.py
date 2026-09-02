from __future__ import annotations

import sys
import unittest
import zipfile
from pathlib import Path

import pandas as pd


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import config as cfg  # noqa: E402
import run_analysis  # noqa: E402


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.full, cls.analysis, cls.screening = run_analysis.load_and_prepare()

    def test_raven_screening_produces_n99(self) -> None:
        self.assertEqual(len(self.full), 101)
        self.assertEqual(int(self.full["raven_flag"].sum()), 2)
        self.assertEqual(len(self.analysis), 99)

    def test_model_dataset_is_pre_only_and_deidentified(self) -> None:
        forbidden = [
            column
            for column in self.analysis
            if str(column).upper().endswith("_POST")
            or "RAVEN" in str(column).upper()
            or str(column).lower() in {"group", "id"}
        ]
        self.assertEqual(forbidden, [])

    def test_exact_outcome_set(self) -> None:
        expected = {
            "CBT_F_SPAN",
            "CBT_B_SPAN",
            "TOL_ACC",
            "TOL_VIO_REG",
            "WM_ACC",
            "PLANNING_ACC",
            "PLANNING_EFF",
            "PWM_ACC",
            "PWM_EFF",
        }
        self.assertEqual({outcome for outcome, _, _ in cfg.OUTCOMES}, expected)
        self.assertNotIn("PLANNING_OST", expected)
        self.assertNotIn("PWM_OST", expected)

    def test_complete_totals_require_all_components(self) -> None:
        for total, components in cfg.COMPLETE_TOTALS.items():
            observed = self.full[f"{total}_components_observed"]
            self.assertTrue(self.full.loc[observed.lt(len(components)), total].isna().all())
            self.assertTrue(self.full.loc[observed.eq(len(components)), total].notna().all())
        self.assertEqual(int(self.analysis["ABAS_TOT_complete"].notna().sum()), 95)
        self.assertEqual(int(self.analysis["BRIEF_TOT_complete"].notna().sum()), 96)

    def test_no_suppongo_predictors(self) -> None:
        predictors = [
            predictor
            for block in cfg.PREDICTOR_BLOCKS.values()
            for predictor in block
        ]
        self.assertFalse(any("supp" in predictor.lower() for predictor in predictors))


class PrimaryModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, analysis, _ = run_analysis.load_and_prepare()
        cls.models = run_analysis.run_primary_models(analysis)

    def test_block_sizes_and_significant_count(self) -> None:
        ok = self.models.loc[self.models["status"].eq("ok")]
        self.assertEqual(len(ok), 216)
        self.assertEqual(ok.groupby("block").size().to_dict(), cfg.EXPECTED_BLOCK_TERMS)
        self.assertEqual(int(ok["significant_fdr05"].sum()), 22)

    def test_formulas_exclude_forbidden_terms(self) -> None:
        formulas = self.models.loc[self.models["status"].eq("ok"), "formula"]
        self.assertFalse(formulas.str.contains("Raven|POST|group", case=False, regex=True).any())

    def test_key_result_replicates(self) -> None:
        row = self.models.loc[
            self.models["block"].eq("abas_subscales")
            & self.models["predictor"].eq("ABAS_fun_acc")
            & self.models["outcome"].eq("CBT_B_SPAN")
        ].iloc[0]
        self.assertAlmostEqual(float(row["beta_standardized"]), 0.3964458, places=5)
        self.assertAlmostEqual(float(row["q_fdr_bh"]), 0.014316, places=5)

    def test_no_ost_outcomes_in_results(self) -> None:
        outcomes = set(self.models["outcome"])
        self.assertNotIn("PLANNING_OST", outcomes)
        self.assertNotIn("PWM_OST", outcomes)


class GeneratedOutputTests(unittest.TestCase):
    def test_expected_outputs_are_aggregate_only(self) -> None:
        workbook = cfg.OUTPUT_ROOT / "analysis_results.xlsx"
        if not workbook.exists():
            self.skipTest("Run scripts/run_analysis.py before checking outputs")
        required = [
            workbook,
            cfg.OUTPUT_ROOT / "analysis_summary.md",
            cfg.TABLE_ROOT / "all_primary_models.csv",
            cfg.TABLE_ROOT / "fdr_significant_models.csv",
            cfg.FIGURE_ROOT / "primary_forest_plot.png",
            cfg.FIGURE_ROOT / "primary_forest_plot.svg",
            cfg.FIGURE_ROOT / "significant_beta_heatmap.png",
            cfg.FIGURE_ROOT / "significant_beta_heatmap.svg",
        ]
        self.assertEqual([path for path in required if not path.exists()], [])
        excel = pd.ExcelFile(workbook)
        for sheet in excel.sheet_names:
            frame = pd.read_excel(workbook, sheet_name=sheet)
            self.assertNotIn("ID", frame.columns)
            self.assertFalse(any(str(column).upper().endswith("_POST") for column in frame.columns))

    def test_rendered_paper_has_only_requested_sections(self) -> None:
        html_path = cfg.PAPER_ROOT / "abasbrief_paper.html"
        docx_path = cfg.PAPER_ROOT / "abasbrief_paper.docx"
        if not html_path.exists() or not docx_path.exists():
            self.skipTest("Run scripts/render_paper.py before checking rendered files")

        html = html_path.read_text(encoding="utf-8")
        self.assertIn("<h1>Methods</h1>", html)
        self.assertIn("<h1>Results</h1>", html)
        self.assertIn(">References</h2>", html)

        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        for requested in ("Methods", "Results", "References"):
            self.assertIn(requested, document_xml)

        for forbidden in ("Abstract", "Introduction", "Discussion", "Conclusion"):
            self.assertNotIn(f">{forbidden}<", html)
            self.assertNotIn(f">{forbidden}<", document_xml)


if __name__ == "__main__":
    unittest.main()
