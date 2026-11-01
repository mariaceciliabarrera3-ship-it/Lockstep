import os
import sys
import tempfile
import unittest

from sandbox.paths import PathEscapeError
from sandbox.runner import ExecutionResult, run_command
from security.secrets import SecretManager

PY = sys.executable


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def run_py(self, code, **kw):
        return run_command([PY, "-c", code], cwd=self.cwd, **kw)

    def test_successful_command(self):
        r = self.run_py("print('hello')")
        self.assertIsInstance(r, ExecutionResult)
        self.assertEqual((r.exit_code, r.stdout.strip()), (0, "hello"))
        self.assertFalse(r.timed_out)
        self.assertFalse(r.truncated)
        self.assertGreaterEqual(r.duration, 0)

    def test_failing_command_keeps_exit_code_and_stderr(self):
        r = self.run_py("import sys; sys.stderr.write('boom'); sys.exit(3)")
        self.assertEqual(r.exit_code, 3)
        self.assertIn("boom", r.stderr)

    def test_runs_inside_the_given_folder(self):
        r = self.run_py("import os; print(os.getcwd())")
        self.assertEqual(r.stdout.strip(), os.path.realpath(self.cwd))

    def test_timeout_kills_the_process(self):
        r = self.run_py("import time; time.sleep(30)", timeout=1)
        self.assertTrue(r.timed_out)
        self.assertEqual(r.exit_code, 124)
        self.assertLess(r.duration, 10)

    def test_timeout_also_kills_child_processes(self):
        code = ("import subprocess, sys, time\n"
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                "time.sleep(30)")
        r = self.run_py(code, timeout=1)
        self.assertTrue(r.timed_out)
        self.assertLess(r.duration, 10)

    def test_output_is_truncated_and_flagged(self):
        r = self.run_py("print('x' * 50000)", max_output=1000)
        self.assertTrue(r.truncated)
        self.assertLess(len(r.stdout), 1200)
        self.assertIn("truncated", r.stdout)

    def test_the_child_cannot_see_the_parents_secrets(self):
        os.environ["LOCKSTEP_TEST_SECRET"] = "top-secret-value"
        try:
            r = self.run_py("import os; print(os.environ.get('LOCKSTEP_TEST_SECRET'))")
        finally:
            del os.environ["LOCKSTEP_TEST_SECRET"]
        self.assertEqual(r.stdout.strip(), "None")

    def test_only_the_stage_secrets_are_passed_in(self):
        r = self.run_py("import os; print(os.environ.get('STAGE_KEY'))",
                        env_extra={"STAGE_KEY": "value-for-this-stage"})
        self.assertEqual(r.stdout.strip(), "value-for-this-stage")

    def test_secrets_are_redacted_from_the_output(self):
        secrets = SecretManager()
        secrets.set("STAGE_KEY", "value-for-this-stage")
        r = self.run_py("import os; print('key=' + os.environ['STAGE_KEY'])",
                        env_extra={"STAGE_KEY": "value-for-this-stage"}, redact=secrets.redact)
        self.assertNotIn("value-for-this-stage", r.stdout)
        self.assertIn("***", r.stdout)

    def test_stdin_is_closed_so_nothing_can_hang_waiting_for_input(self):
        r = self.run_py("import sys; print(repr(sys.stdin.read()))", timeout=5)
        self.assertEqual(r.stdout.strip(), "''")
        self.assertFalse(r.timed_out)

    def test_unknown_command_is_reported_not_raised(self):
        r = run_command(["definitely-not-a-real-command-xyz"], cwd=self.cwd)
        self.assertEqual(r.exit_code, 127)
        self.assertIn("not found", r.stderr)

    def test_shell_strings_are_rejected(self):
        for bad in ("echo hi", "", [], None):
            with self.subTest(repr(bad)):
                with self.assertRaises(ValueError):
                    run_command(bad, cwd=self.cwd)

    def test_missing_working_folder_is_rejected(self):
        with self.assertRaises(ValueError):
            run_command([PY, "-c", "print(1)"], cwd=os.path.join(self.cwd, "nope"))

    def test_working_folder_outside_the_project_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(PathEscapeError):
                run_command([PY, "-c", "print(1)"], cwd=other, root=self.cwd)

    def test_working_folder_inside_the_project_root_is_accepted(self):
        sub = os.path.join(self.cwd, "sub")
        os.makedirs(sub)
        r = run_command([PY, "-c", "print('ok')"], cwd=sub, root=self.cwd)
        self.assertEqual(r.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
