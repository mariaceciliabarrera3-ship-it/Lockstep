import json
import tempfile
import unittest
from pathlib import Path

from agents.architect import create_master_manual
from core.models import Workflow, WorkflowState
from core.persistence import Persistence
from security.secrets import SecretManager


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip(self):
        p = Persistence(self.dir)
        wf = Workflow(project_id="p1", state=WorkflowState.HUMAN_APPROVAL,
                      manual=create_master_manual("n", "python app"),
                      revision_count=2, history=["INTAKE"])
        p.save(wf)
        self.assertEqual(p.load("p1"), wf)

    def test_secret_never_reaches_disk(self):
        secrets = SecretManager()
        secrets.set("TAVILY_API_KEY", "tvly-SECRET-12345")
        p = Persistence(self.dir, redact=secrets.redact)
        wf = Workflow(project_id="p2",
                      manual=create_master_manual(
                          "n", "python app, key tvly-SECRET-12345"))
        p.save(wf)
        raw = Path(self.dir, "p2.json").read_text(encoding="utf-8")
        self.assertNotIn("tvly-SECRET-12345", raw)
        json.loads(raw)  # still valid JSON

    def test_unsafe_project_id_rejected(self):
        with self.assertRaises(ValueError):
            Persistence(self.dir).save(Workflow(project_id="../evil"))

    def test_no_temp_file_left(self):
        p = Persistence(self.dir)
        p.save(Workflow(project_id="p3"))
        self.assertEqual([f.name for f in Path(self.dir).iterdir()], ["p3.json"])

    def test_load_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            Persistence(self.dir).load("nope")


if __name__ == "__main__":
    unittest.main()
