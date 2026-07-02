from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

import paper_config as cfg  # noqa: E402
import run_analysis  # noqa: E402


class BaselineDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset, cls.outcomes, cls.questionnaires = run_analysis.build_baseline_dataset()

    def test_participant_ids_are_unique(self) -> None:
        self.assertEqual(len(self.dataset), 101)
        self.assertEqual(self.dataset["ID"].nunique(), 101)

    def test_no_post_columns_in_baseline_dataset(self) -> None:
        post_columns = [
            column for column in self.dataset.columns if str(column).upper().endswith("_POST")
        ]
        self.assertEqual(post_columns, [])

    def test_required_derived_scores_are_present(self) -> None:
        for column in [
            "ABAS_TOT",
            "ABAS_ASSUMED_TOTAL",
            "BRIEF_TOT",
            "PLANNING_COMPOSITE_PRE",
            "PWM_COMPOSITE_PRE",
        ]:
            self.assertIn(column, self.dataset.columns)

    def test_questionnaire_dictionary_keeps_low_n_variables(self) -> None:
        self.assertIn(
            "ABAS_Selfdirection_suppongo",
            self.questionnaires["questionnaire"].tolist(),
        )
        row = self.questionnaires.loc[
            self.questionnaires["questionnaire"].eq("ABAS_Selfdirection_suppongo")
        ].iloc[0]
        self.assertFalse(bool(row["usable_for_models"]))


class GeneratedOutputTests(unittest.TestCase):
    def test_required_outputs_exist_after_run(self) -> None:
        if not cfg.OUTPUT_ROOT.exists():
            self.skipTest("Run abas_brief_navigation_paper/analysis/run_analysis.py first")
        required = [
            cfg.OUTPUT_ROOT / "00_data" / "baseline_pre_dataset.xlsx",
            cfg.OUTPUT_ROOT / "01_descriptives" / "descriptives.xlsx",
            cfg.OUTPUT_ROOT / "02_correlations" / "abas_brief_pre_correlations.xlsx",
            cfg.OUTPUT_ROOT / "03_regressions" / "abas_brief_pre_regressions.xlsx",
            cfg.OUTPUT_ROOT / "tables" / "paper_results_summary.md",
            cfg.OUTPUT_ROOT / "run_manifest.xlsx",
        ]
        self.assertEqual([path for path in required if not path.exists()], [])


if __name__ == "__main__":
    unittest.main()

