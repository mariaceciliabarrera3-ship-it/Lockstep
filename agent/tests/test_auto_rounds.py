import tempfile
import unittest

from agents.architect import create_master_manual
from core.models import Evaluation, EvaluationStatus, WorkflowState
from core.orchestrator import (MAX_AUTO_ROUNDS, ApprovalError, DesignFailed,
                               Orchestrator)
from core.persistence import Persistence

GOOD = "Build a small Python app that reads a CSV and prints stats"
APPROVE = Evaluation(EvaluationStatus.APPROVE, "ok")


def reject(text="Stage 1: criteria are vague"):
    return Evaluation(EvaluationStatus.REJECT, "problems", [text])


class AutoRoundsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.persistence = Persistence(self._tmp.name)
        self.feedbacks = []

    def tearDown(self):
        self._tmp.cleanup()

    def architect(self, name, objective, feedback=None):
        self.feedbacks.append(feedback)
        return create_master_manual(name, objective, feedback)

    def orch(self, verdicts):
        pending = list(verdicts)

        def evaluator(manual):
            outcome = pending.pop(0) if len(pending) > 1 else pending[0]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return Orchestrator(self.persistence, architect=self.architect, evaluator=evaluator)

    def test_max_auto_rounds_is_two(self):
        self.assertEqual(MAX_AUTO_ROUNDS, 2)

    def test_approved_manual_needs_no_extra_round(self):
        wf = self.orch([APPROVE]).start_project("a1", "csv", GOOD)
        self.assertEqual(len(self.feedbacks), 1)
        self.assertEqual(wf.auto_rounds, 0)
        self.assertEqual(wf.history, ["INTAKE", "ARCHITECTURE", "EVALUATION", "HUMAN_APPROVAL"])

    def test_reject_then_approve_uses_one_round_and_passes_the_corrections(self):
        wf = self.orch([reject("Stage 1: criteria are vague"), APPROVE]).start_project("a2", "csv", GOOD)
        self.assertEqual(len(self.feedbacks), 2)
        self.assertIn("Stage 1: criteria are vague", self.feedbacks[1])
        self.assertEqual(wf.auto_rounds, 1)
        self.assertEqual(wf.evaluation.status, EvaluationStatus.APPROVE)
        self.assertEqual(wf.state, WorkflowState.HUMAN_APPROVAL)
        self.assertEqual(wf.history, ["INTAKE", "ARCHITECTURE", "EVALUATION", "ARCHITECTURE",
                                      "EVALUATION", "HUMAN_APPROVAL"])

    def test_still_rejected_after_two_rounds_reaches_the_human_gate_as_rejected(self):
        orch = self.orch([reject()])
        wf = orch.start_project("a3", "csv", GOOD)
        self.assertEqual(len(self.feedbacks), 1 + MAX_AUTO_ROUNDS)
        self.assertEqual(wf.auto_rounds, MAX_AUTO_ROUNDS)
        self.assertEqual(wf.state, WorkflowState.HUMAN_APPROVAL)
        self.assertEqual(wf.evaluation.status, EvaluationStatus.REJECT)
        with self.assertRaises(ApprovalError):
            orch.approve(wf)

    def test_human_request_for_changes_restarts_the_automatic_rounds(self):
        orch = self.orch([reject()])
        wf = orch.start_project("a4", "csv", GOOD)
        before = len(self.feedbacks)
        orch.request_changes(wf, "make the python app smaller")
        self.assertEqual(len(self.feedbacks) - before, 1 + MAX_AUTO_ROUNDS)
        self.assertIn("make the python app smaller", self.feedbacks[before])
        self.assertEqual(wf.auto_rounds, MAX_AUTO_ROUNDS)

    def test_evaluator_failure_pauses_and_persists(self):
        orch = self.orch([RuntimeError("judge api down")])
        with self.assertRaises(DesignFailed):
            orch.start_project("a5", "csv", GOOD)
        self.assertEqual(self.persistence.load("a5").state, WorkflowState.PAUSED)

    def test_auto_rounds_survive_save_and_load(self):
        orch = self.orch([reject(), APPROVE])
        wf = orch.start_project("a6", "csv", GOOD)
        self.assertEqual(self.persistence.load("a6").auto_rounds, wf.auto_rounds)


if __name__ == "__main__":
    unittest.main()
