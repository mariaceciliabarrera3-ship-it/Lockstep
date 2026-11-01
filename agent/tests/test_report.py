import unittest

from agents.architect import create_master_manual
from core.models import Evaluation, EvaluationStatus, Workflow
from core.report import gate_report


def wf_with(evaluation, rounds=0):
    return Workflow(project_id="r1", manual=create_master_manual("csv-tool", "Read a CSV"),
                    evaluation=evaluation, auto_rounds=rounds)


class GateReportTest(unittest.TestCase):
    def test_lists_project_stages_and_how_to_check(self):
        report = gate_report(wf_with(Evaluation(EvaluationStatus.APPROVE, "ok")))
        self.assertIn("csv-tool", report)
        self.assertIn("Project foundation", report)
        self.assertIn("How to check", report)
        self.assertIn("Dependencies are declared", report)

    def test_approved_manual_says_nothing_happens_without_approval(self):
        report = gate_report(wf_with(Evaluation(EvaluationStatus.APPROVE, "ok")))
        self.assertIn("Nothing is implemented until you approve", report)
        self.assertNotIn("cannot approve", report)

    def test_rejected_manual_shows_corrections_and_blocks_approval(self):
        ev = Evaluation(EvaluationStatus.REJECT, "problems", ["Stage 1: vague criteria"])
        report = gate_report(wf_with(ev))
        self.assertIn("Needs fixing", report)
        self.assertIn("Stage 1: vague criteria", report)
        self.assertIn("cannot approve", report)

    def test_shows_how_many_automatic_rounds_were_used(self):
        report = gate_report(wf_with(Evaluation(EvaluationStatus.APPROVE, "ok"), rounds=1))
        self.assertIn("1 of 2", report)

    def test_no_manual_yet_does_not_crash(self):
        self.assertIsInstance(gate_report(Workflow(project_id="r2")), str)


if __name__ == "__main__":
    unittest.main()
