import json
import os
import unittest

from agents.architect_llm import parse_manual_json
from agents.evaluator import evaluate_manual
from core.models import EvaluationStatus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_cases():
    with open(os.path.join(ROOT, "data", "manual_calibration.json"), encoding="utf-8") as f:
        return json.load(f)


class CalibrationDataTest(unittest.TestCase):
    def test_enough_cases_of_both_kinds(self):
        cases = load_cases()
        self.assertGreaterEqual(sum(c["expected"] == "APPROVE" for c in cases), 5)
        self.assertGreaterEqual(sum(c["expected"] == "REJECT" for c in cases), 7)

    def test_cases_are_well_formed_and_unique(self):
        cases = load_cases()
        names = [c["name"] for c in cases]
        self.assertEqual(len(names), len(set(names)))
        for c in cases:
            self.assertIn(c["expected"], ("APPROVE", "REJECT"))
            self.assertIsInstance(c["manual"], dict)
            if c["expected"] == "REJECT":
                self.assertTrue(c["planted_issue"].strip(), c["name"])

    def test_every_manual_has_a_valid_format(self):
        for c in load_cases():
            with self.subTest(c["name"]):
                parse_manual_json(json.dumps(c["manual"]), "calibration", "calibration")

    def test_the_structural_check_cannot_tell_them_apart(self):
        # Only a semantic judge can separate sound from flawed manuals.
        for c in load_cases():
            with self.subTest(c["name"]):
                manual = parse_manual_json(json.dumps(c["manual"]), "calibration", "calibration")
                self.assertEqual(evaluate_manual(manual).status, EvaluationStatus.APPROVE)


if __name__ == "__main__":
    unittest.main()
