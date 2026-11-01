import json
import os
import tempfile
import unittest

from core.orchestrator import Orchestrator
from core.wiring import build_orchestrator


def valid_config():
    return {"nebius": {"base_url": "https://example.test/v1/"},
            "models": {"classifier": "m-nano", "architect": "m-super",
                       "judge": "m-ultra"}}


class WiringTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self._tmp.name, "state")

    def tearDown(self):
        self._tmp.cleanup()

    def config(self, data):
        path = os.path.join(self._tmp.name, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_missing_config_file_means_offline(self):
        w = build_orchestrator(os.path.join(self._tmp.name, "none.json"), {}, self.state)
        self.assertEqual(w.mode, "OFFLINE")
        self.assertIsInstance(w.orchestrator, Orchestrator)

    def test_placeholder_models_mean_offline(self):
        cfg = valid_config()
        cfg["models"]["architect"] = "FILL"
        w = build_orchestrator(self.config(cfg), {"NEBIUS_API_KEY": "k-123456"}, self.state)
        self.assertEqual(w.mode, "OFFLINE")

    def test_missing_key_means_offline_and_names_the_variable(self):
        w = build_orchestrator(self.config(valid_config()), {}, self.state)
        self.assertEqual(w.mode, "OFFLINE")
        self.assertIn("NEBIUS_API_KEY", w.reason)

    def test_valid_config_and_key_mean_online(self):
        w = build_orchestrator(self.config(valid_config()),
                               {"NEBIUS_API_KEY": "k-123456"}, self.state)
        self.assertEqual(w.mode, "ONLINE")
        self.assertIsInstance(w.orchestrator, Orchestrator)

    def test_other_providers_key_variable_is_never_used(self):
        w = build_orchestrator(self.config(valid_config()),
                               {"NVIDIA_API_KEY": "nvapi-123456"}, self.state)
        self.assertEqual(w.mode, "OFFLINE")

    def test_offline_mode_runs_the_whole_design_phase(self):
        w = build_orchestrator(os.path.join(self._tmp.name, "none.json"), {}, self.state)
        wf = w.orchestrator.start_project(
            "w1", "csv", "Build a small Python app that reads a CSV")
        self.assertEqual(wf.state.value, "HUMAN_APPROVAL")


if __name__ == "__main__":
    unittest.main()
