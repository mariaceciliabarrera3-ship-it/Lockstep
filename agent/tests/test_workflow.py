import tempfile
import unittest

from agents.architect import create_master_manual
from agents.evaluator import evaluate_manual
from core.models import MasterManual, Stage, WorkflowState
from core.orchestrator import (MAX_REVISIONS, ApprovalError, IllegalTransition,
                               Orchestrator, OutOfScopeError)
from core.persistence import Persistence

S = WorkflowState
GOOD = "Build a small Python app that reads a CSV and prints stats"


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.persistence = Persistence(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def orch(self, **kw):
        return Orchestrator(self.persistence, **kw)

    # ---- happy path & scope -------------------------------------------

    def test_happy_path_stops_at_human_gate(self):
        wf = self.orch().start_project("p1", "csv", GOOD)
        self.assertEqual(wf.state, S.HUMAN_APPROVAL)
        self.assertEqual(wf.history,
                         ["INTAKE", "ARCHITECTURE", "EVALUATION", "HUMAN_APPROVAL"])
        self.assertFalse(wf.approved)
        self.assertEqual(self.persistence.load("p1"), wf)

    def test_off_topic_rejected_and_architect_never_called(self):
        def boom(*a, **k):
            raise AssertionError("architect must not run")
        with self.assertRaises(OutOfScopeError):
            self.orch(architect=boom).start_project(
                "p2", "x", "How is your boyfriend?")
        self.assertEqual(self.persistence.load("p2").state, S.IDLE)

    def test_classifier_error_fails_closed(self):
        def broken(_):
            raise RuntimeError("api down")
        with self.assertRaises(OutOfScopeError):
            self.orch(classifier=broken).start_project("p3", "x", GOOD)

    # ---- state machine ------------------------------------------------

    def test_illegal_transition_blocked(self):
        o = self.orch()
        wf = o.start_project("p4", "csv", GOOD)
        with self.assertRaises(IllegalTransition):
            o._go(wf, S.EVALUATION)  # cannot jump from the gate

    def test_context_branch_is_visited_only_when_requested(self):
        def wants_context(name, obj, feedback=None):
            m = create_master_manual(name, obj)
            m.context_requested = True
            return m
        wf = self.orch(architect=wants_context).start_project("p5", "x", GOOD)
        self.assertIn("CONTEXT_RESEARCH", wf.history)
        wf2 = self.orch().start_project("p6", "x", GOOD)
        self.assertNotIn("CONTEXT_RESEARCH", wf2.history)

    # ---- human gate ---------------------------------------------------

    def test_cannot_implement_without_approval(self):
        o = self.orch()
        wf = o.start_project("p7", "csv", GOOD)
        with self.assertRaises(ApprovalError):
            o.begin_implementation(wf)

    def test_approve_then_implement(self):
        o = self.orch()
        wf = o.start_project("p8", "csv", GOOD)
        o.approve(wf)
        o.begin_implementation(wf)
        self.assertEqual(wf.state, S.IMPLEMENTATION)

    def test_cannot_approve_a_rejected_evaluation(self):
        def bad_manual(name, obj, feedback=None):
            return MasterManual(name, obj, ["python"], [])  # no stages
        o = self.orch(architect=bad_manual)
        wf = o.start_project("p9", "x", GOOD)
        self.assertEqual(wf.evaluation.status.value, "REJECT")
        with self.assertRaises(ApprovalError):
            o.approve(wf)

    def test_request_changes_loops_back_then_pauses(self):
        o = self.orch()
        wf = o.start_project("p10", "csv", GOOD)
        o.request_changes(wf, "make the python app smaller")
        self.assertEqual(wf.state, S.HUMAN_APPROVAL)
        self.assertEqual(wf.revision_count, 1)
        for _ in range(MAX_REVISIONS):
            if wf.state == S.PAUSED:
                break
            o.request_changes(wf, "fix the python bug again")
        self.assertEqual(wf.state, S.PAUSED)

    def test_resume_after_interruption(self):
        self.orch().start_project("p11", "csv", GOOD)
        wf = Orchestrator(Persistence(self._tmp.name)).resume("p11")
        self.assertEqual(wf.state, S.HUMAN_APPROVAL)

    # ---- evaluator ----------------------------------------------------

    def test_evaluator_flags_unknown_language_and_bad_numbers(self):
        m = MasterManual("n", "o", ["cobol"],
                         [Stage(2, "a", "obj", acceptance_criteria=["x"],
                                interface_contract=[{"kind": "file", "name": "a.py", "description": "x"}])])
        ev = evaluate_manual(m)
        self.assertEqual(ev.status.value, "REJECT")
        self.assertEqual(len(ev.corrections), 2)


if __name__ == "__main__":
    unittest.main()
