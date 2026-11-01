import os
import shutil
import tempfile
import unittest

from sandbox.paths import PathEscapeError
from sandbox.workspace import Workspace, WorkspaceError, path_allowed

HAS_GIT = shutil.which("git") is not None


class PathAllowedTest(unittest.TestCase):
    def test_exact_files_and_folder_prefixes(self):
        allowed = ["app.py", "src/util.py", "tests/"]
        self.assertTrue(path_allowed("app.py", allowed))
        self.assertTrue(path_allowed("src/util.py", allowed))
        self.assertTrue(path_allowed("tests/test_app.py", allowed))
        self.assertTrue(path_allowed("tests/deep/x.py", allowed))

    def test_everything_else_is_outside(self):
        allowed = ["app.py", "tests/"]
        for bad in ("other.py", "src/app.py", "tests", "testsX/a.py", "../app.py", ""):
            with self.subTest(bad):
                self.assertFalse(path_allowed(bad, allowed))

    def test_dot_slash_is_normalized(self):
        self.assertTrue(path_allowed("./app.py", ["app.py"]))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(os.path.join(self._tmp.name, "project"))
        self.ws.init()

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_fresh_workspace_has_no_changes(self):
        self.assertEqual(self.ws.changed_files(), [])

    def test_write_and_read_a_file_including_nested_folders(self):
        self.ws.write_file("src/pkg/mod.py", "x = 1\n")
        self.assertEqual(self.ws.read_file("src/pkg/mod.py"), "x = 1\n")
        self.assertTrue(os.path.isfile(os.path.join(self.ws.root, "src", "pkg", "mod.py")))

    def test_reading_a_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.ws.read_file("nope.py")

    def test_writing_outside_the_project_is_impossible(self):
        outside = os.path.join(self._tmp.name, "outside")
        os.makedirs(outside)
        os.symlink(outside, os.path.join(self.ws.root, "link"))
        for bad in ("../evil.py", os.path.join(outside, "evil.py"), "link/evil.py"):
            with self.subTest(bad):
                with self.assertRaises(PathEscapeError):
                    self.ws.write_file(bad, "boom")
        self.assertEqual(os.listdir(outside), [])

    def test_changed_files_lists_new_and_modified_files(self):
        self.ws.write_file("a.py", "a = 1\n")
        self.ws.commit_stage(1, "first")
        self.ws.write_file("a.py", "a = 2\n")
        self.ws.write_file("sub/b.py", "b = 1\n")
        self.assertEqual(self.ws.changed_files(), ["a.py", "sub/b.py"])

    def test_check_scope_reports_files_outside_the_allowed_list(self):
        self.ws.write_file("app.py", "1\n")
        self.ws.write_file("tests/test_app.py", "2\n")
        self.ws.write_file("secret_notes.txt", "3\n")
        self.assertEqual(self.ws.check_scope(["app.py", "tests/"]), ["secret_notes.txt"])
        self.assertEqual(self.ws.check_scope(["app.py", "tests/", "secret_notes.txt"]), [])

    def test_commit_stage_commits_and_tags(self):
        self.ws.write_file("a.py", "a = 1\n")
        commit = self.ws.commit_stage(1, "first stage")
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertEqual(self.ws.changed_files(), [])
        tags = self.ws._git("tag").split()
        self.assertIn("stage-1", tags)

    def test_commit_stage_with_nothing_to_commit_still_works(self):
        first = self.ws.commit_stage(1)
        second = self.ws.commit_stage(2)
        self.assertRegex(second, r"^[0-9a-f]{40}$")
        self.assertNotEqual(first, second)

    def test_revert_restores_the_last_committed_state(self):
        self.ws.write_file("a.py", "good\n")
        self.ws.commit_stage(1)
        self.ws.write_file("a.py", "broken\n")
        self.ws.write_file("junk.py", "junk\n")
        self.ws.revert_to_last_commit()
        self.assertEqual(self.ws.read_file("a.py"), "good\n")
        self.assertFalse(os.path.exists(os.path.join(self.ws.root, "junk.py")))
        self.assertEqual(self.ws.changed_files(), [])

    def test_diff_shows_modified_and_new_files(self):
        self.ws.write_file("a.py", "old line\n")
        self.ws.commit_stage(1)
        self.ws.write_file("a.py", "new line\n")
        self.ws.write_file("b.py", "brand new\n")
        diff = self.ws.diff()
        self.assertIn("-old line", diff)
        self.assertIn("+new line", diff)
        self.assertIn("+brand new", diff)

    def test_git_commands_do_not_see_the_parents_secrets(self):
        os.environ["LOCKSTEP_TEST_SECRET"] = "top-secret"
        try:
            self.ws.write_file("a.py", "1\n")
            self.ws.commit_stage(1)  # must work with a stripped environment
        finally:
            del os.environ["LOCKSTEP_TEST_SECRET"]

    def test_a_failing_git_command_raises_workspace_error(self):
        with self.assertRaises(WorkspaceError):
            self.ws._git("definitely-not-a-git-command")


if __name__ == "__main__":
    unittest.main()
