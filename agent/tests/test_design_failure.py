import tempfile
import unittest

from agents.evaluator import evaluate_manual
from agents.architect import create_master_manual
from core.llm import make_llm_call
from core.models import WorkflowState
from core.orchestrator import DesignFailed, Orchestrator
from core.persistence import Persistence

GOOD = "Build a small Python app that reads a CSV and prints stats"


class DesignFailureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.persistence = Persistence(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_architect_failure_pauses_and_persists(self):
        def broken(name, objective, feedback=None):
            raise RuntimeError("api down")
        orch = Orchestrator(self.persistence, architect=broken)
        with self.assertRaises(DesignFailed):
            orch.start_project("d1", "csv", GOOD)
        self.assertEqual(self.persistence.load("d1").state, WorkflowState.PAUSED)

    def test_architect_failure_during_revision_also_pauses(self):
        calls = {"n": 0}

        def flaky(name, objective, feedback=None):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("api down")
            return create_master_manual(name, objective, feedback)

        orch = Orchestrator(self.persistence, architect=flaky)
        wf = orch.start_project("d2", "csv", GOOD)
        with self.assertRaises(DesignFailed):
            orch.request_changes(wf, "make the python app smaller")
        self.assertEqual(wf.state, WorkflowState.PAUSED)

    def test_evaluator_requires_an_interface_contract(self):
        manual = create_master_manual("n", "python app")
        manual.stages[0].interface_contract = []
        ev = evaluate_manual(manual)
        self.assertEqual(ev.status.value, "REJECT")
        self.assertTrue(any("interface contract" in c for c in ev.corrections))

    def test_stub_architect_manual_is_approved(self):
        self.assertEqual(
            evaluate_manual(create_master_manual("n", "python app")).status.value, "APPROVE")


class FakeClient:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages, max_tokens=1024, temperature=0.0, extra=None):
        self.calls.append((model, messages, max_tokens, temperature, extra))

        class Reply:
            content = "answer"
        return Reply()


class MakeLlmCallTest(unittest.TestCase):
    def test_returns_text_and_passes_settings(self):
        client = FakeClient()
        call = make_llm_call(client, "m-super", max_tokens=4096, extra={"a": 1})
        self.assertEqual(call("hello"), "answer")
        model, messages, max_tokens, temperature, extra = client.calls[0]
        self.assertEqual(model, "m-super")
        self.assertEqual(messages, [{"role": "user", "content": "hello"}])
        self.assertEqual(max_tokens, 4096)
        self.assertEqual(temperature, 0.0)
        self.assertEqual(extra, {"a": 1})


if __name__ == "__main__":
    unittest.main()
