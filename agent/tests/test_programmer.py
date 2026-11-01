import json
import os
import shutil
import tempfile
import unittest

from agents.programmer import (ApplyResult, ProgrammerFormatError, ScopeViolation,
                               apply_changes, build_programmer_prompt,
                               make_model_programmer, parse_programmer_output)
from core.models import Stage
from sandbox.workspace import Workspace

HAS_GIT = shutil.which("git") is not None


def text(data):
    return json.dumps(data)


def stage(**over):
    base = dict(number=2, name="Statistics", objective="Compute the mean of a column",
                requirements=["no external libraries"], files=["stats.py", "tests/"],
                acceptance_criteria=["mean([1,2,3]) returns 2.0"],
                interface_contract=[{"kind": "function", "name": "mean(values: list[float]) -> float",
                                     "description": "arithmetic mean"}])
    base.update(over)
    return Stage(**base)


class ParseOutputTest(unittest.TestCase):
    def test_full_file_and_edits(self):
        data = {"files": [{"path": "a.py", "content": "x = 1\n"},
                          {"path": "b.py", "edits": [{"search": "old", "replace": "new"}]}],
                "notes": "done"}
        changes, notes = parse_programmer_output(text(data))
        self.assertEqual(changes[0], {"path": "a.py", "content": "x = 1\n"})
        self.assertEqual(changes[1]["edits"], [{"search": "old", "replace": "new"}])
        self.assertEqual(notes, "done")

    def test_fences_reasoning_and_prose_are_tolerated(self):
        data = {"files": [{"path": "a.py", "content": "x = 1\n"}]}
        wrapped = "<think>plan {x}</think>\nHere:\n```json\n" + text(data) + "\n```"
        self.assertEqual(len(parse_programmer_output(wrapped)[0]), 1)

    def test_invalid_outputs_are_rejected(self):
        ok = {"path": "a.py", "content": "x"}
        bad = {
            "not json": "here is some code: print(1)",
            "empty": "",
            "no files": text({"files": []}),
            "files not a list": text({"files": "a.py"}),
            "entry not an object": text({"files": ["a.py"]}),
            "empty path": text({"files": [{"path": " ", "content": "x"}]}),
            "no content or edits": text({"files": [{"path": "a.py"}]}),
            "both content and edits": text({"files": [{**ok, "edits": [{"search": "a", "replace": "b"}]}]}),
            "content not a string": text({"files": [{"path": "a.py", "content": 5}]}),
            "edits empty": text({"files": [{"path": "a.py", "edits": []}]}),
            "edit without search": text({"files": [{"path": "a.py", "edits": [{"replace": "b"}]}]}),
            "edit with empty search": text({"files": [{"path": "a.py", "edits": [{"search": "", "replace": "b"}]}]}),
            "edit replace not a string": text({"files": [{"path": "a.py", "edits": [{"search": "a", "replace": 1}]}]}),
        }
        for label, raw in bad.items():
            with self.subTest(label):
                with self.assertRaises(ProgrammerFormatError):
                    parse_programmer_output(raw)


class PromptTest(unittest.TestCase):
    def test_prompt_contains_the_stage_and_the_rules(self):
        prompt = build_programmer_prompt(stage(), {"stats.py": "def mean(v): pass\n"},
                                         feedback="handle empty lists")
        for needle in ("Statistics", "Compute the mean of a column", "no external libraries",
                       "mean([1,2,3]) returns 2.0", "mean(values: list[float]) -> float",
                       "stats.py", "tests/", "def mean(v): pass", "handle empty lists",
                       "search", "replace", "JSON", "secret"):
            self.assertIn(needle, prompt)

    def test_prompt_without_feedback_or_files(self):
        prompt = build_programmer_prompt(stage(), {})
        self.assertNotIn("Feedback to address", prompt)


@unittest.skipUnless(HAS_GIT, "git is not installed")
class ApplyAndProgrammerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(os.path.join(self._tmp.name, "project"))
        self.ws.init()
        self.allowed = ["stats.py", "tests/"]

    def tearDown(self):
        self._tmp.cleanup()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.ws.root, rel))

    def test_new_files_inside_the_scope_are_written(self):
        result = apply_changes(self.ws, [{"path": "stats.py", "content": "def mean(v): ...\n"},
                                         {"path": "tests/test_stats.py", "content": "pass\n"}],
                               self.allowed, notes="ok")
        self.assertIsInstance(result, ApplyResult)
        self.assertEqual(result.written, ["stats.py", "tests/test_stats.py"])
        self.assertEqual(result.notes, "ok")
        self.assertEqual(self.ws.read_file("stats.py"), "def mean(v): ...\n")

    def test_edits_replace_exactly_one_occurrence(self):
        self.ws.write_file("stats.py", "def mean(v):\n    return 0\n")
        apply_changes(self.ws, [{"path": "stats.py",
                                 "edits": [{"search": "return 0", "replace": "return sum(v) / len(v)"}]}],
                      self.allowed)
        self.assertIn("return sum(v) / len(v)", self.ws.read_file("stats.py"))

    def test_edits_fail_if_the_text_is_missing_or_ambiguous(self):
        self.ws.write_file("stats.py", "x = 1\nx = 1\n")
        for search in ("not there", "x = 1"):
            with self.subTest(search):
                with self.assertRaises(ProgrammerFormatError):
                    apply_changes(self.ws, [{"path": "stats.py",
                                             "edits": [{"search": search, "replace": "y"}]}],
                                  self.allowed)
        self.assertEqual(self.ws.read_file("stats.py"), "x = 1\nx = 1\n")

    def test_editing_a_file_that_does_not_exist_fails(self):
        with self.assertRaises(ProgrammerFormatError):
            apply_changes(self.ws, [{"path": "stats.py",
                                     "edits": [{"search": "a", "replace": "b"}]}], self.allowed)

    def test_two_edits_to_the_same_file_apply_in_order(self):
        self.ws.write_file("stats.py", "a = 1\nb = 2\n")
        apply_changes(self.ws, [{"path": "stats.py", "edits": [{"search": "a = 1", "replace": "a = 10"}]},
                                {"path": "stats.py", "edits": [{"search": "b = 2", "replace": "b = 20"}]}],
                      self.allowed)
        self.assertEqual(self.ws.read_file("stats.py"), "a = 10\nb = 20\n")

    def test_a_change_outside_the_scope_is_rejected_and_nothing_is_written(self):
        changes = [{"path": "stats.py", "content": "ok\n"},
                   {"path": "auth.py", "content": "evil\n"}]
        with self.assertRaises(ScopeViolation) as ctx:
            apply_changes(self.ws, changes, self.allowed)
        self.assertEqual(ctx.exception.paths, ["auth.py"])
        self.assertFalse(self.exists("stats.py"))
        self.assertFalse(self.exists("auth.py"))

    def test_path_tricks_are_rejected_as_out_of_scope(self):
        for bad in ("../evil.py", "tests/../auth.py", "/tmp/evil.py", "./auth.py"):
            with self.subTest(bad):
                with self.assertRaises(ScopeViolation):
                    apply_changes(self.ws, [{"path": bad, "content": "x\n"}], self.allowed)

    def test_git_confirms_that_only_allowed_files_changed(self):
        apply_changes(self.ws, [{"path": "stats.py", "content": "ok\n"}], self.allowed)
        self.assertEqual(self.ws.check_scope(self.allowed), [])

    # ---- make_model_programmer -------------------------------------------------
    def llm(self, answers):
        pending, calls = list(answers), []

        def llm_call(prompt):
            calls.append(prompt)
            return pending.pop(0)
        llm_call.calls = calls
        return llm_call

    def good_answer(self):
        return text({"files": [{"path": "stats.py", "content": "def mean(v):\n    return sum(v)/len(v)\n"},
                               {"path": "tests/test_stats.py", "content": "import unittest\n"}],
                     "notes": "implemented"})

    def test_the_programmer_writes_the_stage_files(self):
        llm = self.llm([self.good_answer()])
        result = make_model_programmer(llm)(stage(), self.ws)
        self.assertEqual(result.written, ["stats.py", "tests/test_stats.py"])
        self.assertEqual(result.notes, "implemented")
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(self.ws.check_scope(stage().files), [])

    def test_existing_allowed_files_are_shown_to_the_model(self):
        self.ws.write_file("stats.py", "# existing marker\n")
        llm = self.llm([self.good_answer()])
        make_model_programmer(llm)(stage(), self.ws)
        self.assertIn("# existing marker", llm.calls[0])

    def test_feedback_reaches_the_prompt(self):
        llm = self.llm([self.good_answer()])
        make_model_programmer(llm)(stage(), self.ws, feedback="handle empty lists")
        self.assertIn("handle empty lists", llm.calls[0])

    def test_one_retry_with_the_error_message_then_it_gives_up(self):
        llm = self.llm(["garbage", self.good_answer()])
        make_model_programmer(llm)(stage(), self.ws)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("previous answer was invalid", llm.calls[1])
        llm2 = self.llm(["garbage", "more garbage"])
        with self.assertRaises(ProgrammerFormatError):
            make_model_programmer(llm2)(stage(), self.ws)
        self.assertEqual(len(llm2.calls), 2)

    def test_a_bad_edit_triggers_the_retry_too(self):
        bad = text({"files": [{"path": "stats.py", "edits": [{"search": "x", "replace": "y"}]}]})
        llm = self.llm([bad, self.good_answer()])
        make_model_programmer(llm)(stage(), self.ws)
        self.assertEqual(len(llm.calls), 2)

    def test_out_of_scope_output_is_not_retried_and_writes_nothing(self):
        evil = text({"files": [{"path": "stats.py", "content": "ok\n"},
                               {"path": "config.json", "content": "{}\n"}]})
        llm = self.llm([evil, self.good_answer()])
        with self.assertRaises(ScopeViolation):
            make_model_programmer(llm)(stage(), self.ws)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(self.ws.changed_files(), [])

    def test_api_errors_are_not_swallowed(self):
        def boom(prompt):
            raise RuntimeError("api down")
        with self.assertRaises(RuntimeError):
            make_model_programmer(boom)(stage(), self.ws)


if __name__ == "__main__":
    unittest.main()
