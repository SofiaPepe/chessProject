from __future__ import annotations

import unittest
from pathlib import Path

from openpyxl import load_workbook

from scoring import (
    COMPLETE_DATABASE,
    OFFICIAL_DATABASE,
    canonical_project_id,
    is_legacy_minefield_column,
)
from shortest_path import parse_coordinate, shortest_path


class ProjectScoringUnitTests(unittest.TestCase):
    def test_project_id_normalization(self) -> None:
        self.assertEqual(canonical_project_id("ppr7"), "PPR07")
        self.assertEqual(canonical_project_id("SPR01"), "SPR1")
        self.assertEqual(canonical_project_id("AC 09"), "AC09")
        self.assertEqual(canonical_project_id("PROVA"), "")

    def test_shortest_path_uses_orthogonal_grid(self) -> None:
        start = parse_coordinate("A1")
        stop = parse_coordinate("C1")
        path = shortest_path(start, stop, {parse_coordinate("B1")})
        self.assertIsNotNone(path)
        self.assertEqual(len(path) - 1, 4)


class CompleteDatabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not Path(COMPLETE_DATABASE).exists():
            raise unittest.SkipTest("Run scoring.py before integration tests")

        source_book = load_workbook(
            OFFICIAL_DATABASE,
            read_only=True,
            data_only=True,
        )
        source_sheet = source_book[source_book.sheetnames[0]]
        cls.source_headers = [
            str(value).strip() if value is not None else ""
            for value in next(source_sheet.iter_rows(values_only=True))
        ]
        cls.source_rows = [
            dict(zip(cls.source_headers, row))
            for row in source_sheet.iter_rows(min_row=2, values_only=True)
            if row[0]
        ]
        source_book.close()

        output_book = load_workbook(
            COMPLETE_DATABASE,
            read_only=True,
            data_only=True,
        )
        output_sheet = output_book["complete_database"]
        cls.output_headers = list(
            next(output_sheet.iter_rows(values_only=True))
        )
        cls.output_rows = [
            dict(zip(cls.output_headers, row))
            for row in output_sheet.iter_rows(min_row=2, values_only=True)
            if row[0]
        ]
        coverage_sheet = output_book["id_coverage"]
        coverage_headers = list(
            next(coverage_sheet.iter_rows(values_only=True))
        )
        cls.coverage_rows = [
            dict(zip(coverage_headers, row))
            for row in coverage_sheet.iter_rows(min_row=2, values_only=True)
        ]
        output_book.close()

    def test_all_official_ids_are_retained_once(self) -> None:
        source_ids = [row["ID"] for row in self.source_rows]
        output_ids = [row["ID"] for row in self.output_rows]
        self.assertEqual(output_ids, source_ids)
        self.assertEqual(len(output_ids), 101)
        self.assertEqual(len(set(output_ids)), 101)

    def test_database_contains_only_recalculated_minefield_fields(self) -> None:
        minefield_fields = [
            header
            for header in self.output_headers
            if str(header).startswith("MF_")
        ]
        self.assertEqual(len(minefield_fields), 34)
        self.assertFalse(
            any(
                is_legacy_minefield_column(str(header))
                for header in self.output_headers
            )
        )

    def test_non_minefield_values_are_unchanged(self) -> None:
        retained = [
            header
            for header in self.source_headers
            if not is_legacy_minefield_column(header)
        ]
        output_by_id = {row["ID"]: row for row in self.output_rows}
        for source in self.source_rows:
            output = output_by_id[source["ID"]]
            for header in retained:
                self.assertEqual(output[header], source[header])

    def test_participants_without_raw_data_are_blank(self) -> None:
        expected_missing = {"EXP01", "EXP09", "EXP11", "EXP13", "EXP14"}
        actual_missing = {
            row["participant_id"]
            for row in self.coverage_rows
            if row["status"] == "missing_raw"
        }
        self.assertEqual(actual_missing, expected_missing)

        score_fields = [
            header
            for header in self.output_headers
            if str(header).startswith("MF_")
        ]
        output_by_id = {row["ID"]: row for row in self.output_rows}
        for participant_id in expected_missing:
            self.assertTrue(
                all(
                    output_by_id[participant_id][field] is None
                    for field in score_fields
                )
            )


if __name__ == "__main__":
    unittest.main()
