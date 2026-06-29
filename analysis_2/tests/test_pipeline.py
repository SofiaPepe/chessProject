from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

from common import build_analysis_dataset, find_prepost_pairs  # noqa: E402
from config import INPUT_DATABASE, OUTPUT_ROOT  # noqa: E402


class AnalysisDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.df = build_analysis_dataset()

    def test_recalculated_database_exists(self) -> None:
        self.assertTrue(INPUT_DATABASE.exists())

    def test_participant_ids_are_unique(self) -> None:
        self.assertEqual(len(self.df), 101)
        self.assertEqual(self.df["ID"].nunique(), 101)

    def test_recalculated_minefield_contract_is_present(self) -> None:
        self.assertEqual(len(self.df.columns.intersection(["PLANNING_PERC_PRE", "PLANNING_PERC_POST", "PWM_PERC_PRE", "PWM_PERC_POST"])), 4)
        self.assertIn("WM_ACC_PRE", self.df)
        self.assertIn("PLANNING_PERC_POST", self.df)

    def test_prepost_pairs_include_neuropsych_and_minefield(self) -> None:
        variables = {pair["variable"] for pair in find_prepost_pairs(self.df)}
        self.assertIn("CBT_F_SPAN", variables)
        self.assertIn("WM_ACC", variables)
        self.assertIn("PLANNING_COMPOSITE", variables)
        self.assertIn("WM_TRIAL", variables)


class GeneratedOutputTests(unittest.TestCase):
    def test_required_outputs_exist_after_run(self) -> None:
        if not OUTPUT_ROOT.exists():
            self.skipTest("Run analysis_2/run_all.py first")
        required = [
            OUTPUT_ROOT / "00_data" / "analysis_dataset.xlsx",
            OUTPUT_ROOT / "01_descriptives" / "descriptive_statistics.xlsx",
            OUTPUT_ROOT / "02_baseline" / "baseline_checks.xlsx",
            OUTPUT_ROOT / "02_baseline" / "pre_measures_age_sex.xlsx",
            OUTPUT_ROOT / "03_correlations" / "correlations.xlsx",
            OUTPUT_ROOT / "04_training_effect" / "training_effect_results.xlsx",
            OUTPUT_ROOT / "05_effectiveness" / "treatment_effectiveness.xlsx",
            OUTPUT_ROOT / "06_predictors" / "predictor_models.xlsx",
            OUTPUT_ROOT / "07_pca" / "pca_results.xlsx",
            OUTPUT_ROOT / "run_manifest.xlsx",
        ]
        self.assertEqual([path for path in required if not path.exists()], [])


if __name__ == "__main__":
    unittest.main()
