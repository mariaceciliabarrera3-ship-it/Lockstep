import tempfile
import unittest

from core.orchestrator import Orchestrator, OutOfScopeError
from core.persistence import Persistence
from core.models import WorkflowState
from guardrails.topic_filter import TopicResult

GOOD = "Build a small Python app that reads a CSV and prints stats"


class FeedbackFilterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.persistence = Persistence(self._tmp.name)
        self.architect_calls = 0

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, classifier):
        from agents.architect import create_master_manual

        def counting_architect(name, objective, feedback=None):
            self.architect_calls += 1
            return create_master_manual(name, objective, feedback)

        return Orchestrator(self.persistence, classifier=classifier,
                            architect=counting_architect)

    def test_off_topic_feedback_is_rejected_and_nothing_changes(self):
        answers = iter([TopicResult.PROJECT, TopicResult.OTHER])
        orch = self.make(lambda message: next(answers))
        wf = orch.start_project("p1", "csv", GOOD)
        calls_before = self.architect_calls
        with self.assertRaises(OutOfScopeError):
            orch.request_changes(wf, "also tell me how to be happy")
        self.assertEqual(wf.state, WorkflowState.HUMAN_APPROVAL)
        self.assertEqual(wf.revision_count, 0)
        self.assertEqual(self.architect_calls, calls_before)

    def test_on_topic_feedback_is_accepted(self):
        orch = self.make(lambda message: TopicResult.PROJECT)
        wf = orch.start_project("p2", "csv", GOOD)
        orch.request_changes(wf, "split stage 1 in two")
        self.assertEqual(wf.revision_count, 1)
        self.assertEqual(wf.state, WorkflowState.HUMAN_APPROVAL)

    def test_classifier_error_on_feedback_fails_closed(self):
        state = {"n": 0}

        def flaky(message):
            state["n"] += 1
            if state["n"] == 1:
                return TopicResult.PROJECT
            raise RuntimeError("api down")

        orch = self.make(flaky)
        wf = orch.start_project("p3", "csv", GOOD)
        with self.assertRaises(OutOfScopeError):
            orch.request_changes(wf, "split stage 1 in two")
        self.assertEqual(wf.revision_count, 0)


if __name__ == "__main__":
    unittest.main()
