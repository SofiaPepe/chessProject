from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

import paper_config as cfg  # noqa: E402
import dedicated_models  # noqa: E402
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


class DedicatedModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset, _, _ = run_analysis.build_baseline_dataset()
        cls.dataset = dedicated_models.add_complete_totals_and_screening(dataset)
        cls.outcomes = dedicated_models.outcome_dictionary(cls.dataset)

    def test_raven_screening_defines_primary_n99(self) -> None:
        self.assertEqual(int(self.dataset["raven_screen_flag"].sum()), 2)
        self.assertEqual(int(self.dataset["included_primary_n99"].sum()), 99)

    def test_complete_totals_require_every_standard_scale(self) -> None:
        for total, components in dedicated_models.COMPLETE_TOTALS.items():
            observed = self.dataset[f"{total}_components_observed"]
            self.assertTrue(
                self.dataset.loc[observed.lt(len(components)), total].isna().all()
            )
            self.assertTrue(
                self.dataset.loc[observed.eq(len(components)), total].notna().all()
            )
        self.assertEqual(int(self.dataset["ABAS_TOT_complete"].notna().sum()), 97)
        self.assertEqual(int(self.dataset["BRIEF_TOT_complete"].notna().sum()), 98)

    def test_curated_outcomes_exclude_raven_and_duplicates(self) -> None:
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
        self.assertEqual(len(self.outcomes), 9)
        self.assertEqual(set(self.outcomes["outcome"]), expected)
        self.assertFalse(
            self.outcomes["outcome"].str.contains("RAVEN", case=False).any()
        )
        self.assertNotIn("TOL_TE", self.outcomes["outcome"].tolist())
        self.assertNotIn("TOL_TE_LN", self.outcomes["outcome"].tolist())
        self.assertNotIn("PLANNING_COMPOSITE", self.outcomes["outcome"].tolist())
        self.assertNotIn("PLANNING_OST", self.outcomes["outcome"].tolist())
        self.assertNotIn("PWM_OST", self.outcomes["outcome"].tolist())

    def test_eff_outcome_audit_documents_negative_values(self) -> None:
        audit = self.outcomes.set_index("outcome")
        self.assertEqual(int(audit.loc["PLANNING_EFF", "n_negative_full"]), 1)
        self.assertEqual(int(audit.loc["PWM_EFF", "n_negative_full"]), 3)
        self.assertEqual(audit.loc["PLANNING_EFF", "direction"], "lower_better")
        self.assertEqual(audit.loc["PWM_EFF", "direction"], "lower_better")

    def test_pwm_ost_distribution_audit(self) -> None:
        audit = dedicated_models.pwm_ost_distribution_audit(self.dataset)
        summary = audit["summary"].set_index("sample_scope")
        full = summary.loc["full_n101"]
        primary = summary.loc["primary_n99"]
        self.assertEqual(int(full["n_observed"]), 96)
        self.assertEqual(int(primary["n_observed"]), 94)
        self.assertEqual((int(full["minimum"]), int(full["maximum"])), (2, 7))
        self.assertEqual(int(full["n_above_iqr_fence"]), 4)
        self.assertGreater(float(full["spearman_rho_with_pwm_trial"]), 0.80)

    def test_dedicated_predictor_blocks_have_expected_sizes(self) -> None:
        self.assertEqual(len(dedicated_models.ABAS_STANDARD_SCALES), 8)
        self.assertEqual(len(dedicated_models.BRIEF_STANDARD_SCALES), 9)
        self.assertEqual(len(dedicated_models.BRIEF_INDICES), 3)
        self.assertFalse(
            any(
                "supp" in predictor.lower()
                for predictors in dedicated_models.PREDICTOR_BLOCKS.values()
                for predictor in predictors
            )
        )

    def test_paired_raven_models_use_identical_cases(self) -> None:
        primary = self.dataset.loc[self.dataset["included_primary_n99"]]
        rows = dedicated_models.fit_model_pair(
            primary,
            sample_scope="primary_n99",
            block="totals_separate",
            model_type="separate",
            outcome="CBT_B_SPAN",
            pre_col="CBT_B_SPAN_PRE",
            outcome_family="corsi",
            predictors=["ABAS_TOT_complete"],
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["status"] for row in rows}, {"ok"})
        self.assertEqual(len({row["n"] for row in rows}), 1)


class GeneratedOutputTests(unittest.TestCase):
    def test_required_outputs_exist_after_run(self) -> None:
        if not cfg.OUTPUT_ROOT.exists():
            self.skipTest("Run abas_brief_navigation_paper/analysis/run_analysis.py first")
        required = [
            cfg.OUTPUT_ROOT / "00_data" / "baseline_pre_dataset.xlsx",
            cfg.OUTPUT_ROOT / "01_descriptives" / "descriptives.xlsx",
            cfg.OUTPUT_ROOT / "02_correlations" / "abas_brief_pre_correlations.xlsx",
            cfg.OUTPUT_ROOT / "03_regressions" / "abas_brief_pre_regressions.xlsx",
            cfg.OUTPUT_ROOT / "04_totals_subscales" / "totals_subscales_models.xlsx",
            cfg.OUTPUT_ROOT / "tables" / "dedicated_totals_subscales_comparison.csv",
            cfg.OUTPUT_ROOT / "tables" / "dedicated_totals_subscales_significant.csv",
            cfg.OUTPUT_ROOT / "tables" / "dedicated_n99_with_raven_results.csv",
            cfg.OUTPUT_ROOT / "tables" / "dedicated_n101_with_raven_results.csv",
            cfg.OUTPUT_ROOT / "tables" / "pwm_ost_distribution_audit.csv",
            cfg.OUTPUT_ROOT / "tables" / "dedicated_totals_subscales_summary.md",
            cfg.OUTPUT_ROOT / "tables" / "paper_results_summary.md",
            cfg.OUTPUT_ROOT / "run_manifest.xlsx",
        ]
        self.assertEqual([path for path in required if not path.exists()], [])


if __name__ == "__main__":
    unittest.main()

