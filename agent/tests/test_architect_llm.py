import json
import tempfile
import unittest

from agents.architect_llm import (ManualFormatError, build_architect_prompt,
                                  make_model_architect, parse_manual_json)
from core.models import Workflow
from core.persistence import Persistence


def good_stage(n=1, **over):
    stage = {
        "number": n, "name": f"Stage {n}", "objective": "Do the thing",
        "requirements": ["r1"], "files": ["app.py"], "dependencies": [],
        "inputs": ["input.csv"], "outputs": ["summary.txt"],
        "acceptance_criteria": ["prints a summary"], "tests": ["test_summary"],
        "risks": ["empty file"],
        "interface_contract": [{"kind": "function", "name": "summarize(path)",
                                "description": "returns a dict of statistics"}],
        "secrets": [],
    }
    stage.update(over)
    return stage


def good(**over):
    data = {"language_profiles": ["python"], "context_requested": False,
            "context_reason": None, "stages": [good_stage(1), good_stage(2)]}
    data.update(over)
    return data


def as_text(data):
    return json.dumps(data)


class ParseManualTest(unittest.TestCase):
    def parse(self, text):
        return parse_manual_json(text, "csv-tool", "Read a CSV and print stats")

    def test_valid_manual(self):
        m = self.parse(as_text(good()))
        self.assertEqual(len(m.stages), 2)
        self.assertEqual(m.stages[0].interface_contract[0]["name"], "summarize(path)")
        self.assertEqual(m.generated_by, "model")
        self.assertEqual(m.language_profiles, ["python"])

    def test_name_and_objective_come_from_the_user_not_the_model(self):
        data = good(project_name="evil", objective="evil")
        m = self.parse(as_text(data))
        self.assertEqual(m.project_name, "csv-tool")
        self.assertEqual(m.objective, "Read a CSV and print stats")

    def test_json_inside_markdown_fences(self):
        self.assertEqual(len(self.parse("```json\n" + as_text(good()) + "\n```").stages), 2)

    def test_reasoning_block_and_prose_around_json(self):
        text = "<think>plan {not json}</think>\nHere is the manual:\n" + as_text(good()) + "\nDone."
        self.assertEqual(len(self.parse(text).stages), 2)

    def test_secrets_are_names_only(self):
        data = good()
        data["stages"][0]["secrets"] = [{"name": "TAVILY_API_KEY",
                                         "purpose": "search", "source": "tavily.com"}]
        m = self.parse(as_text(data))
        self.assertEqual(m.stages[0].secrets[0].name, "TAVILY_API_KEY")

    def test_secret_with_a_value_is_rejected(self):
        data = good()
        data["stages"][0]["secrets"] = [{"name": "K", "value": "sk-123456"}]
        with self.assertRaises(ManualFormatError):
            self.parse(as_text(data))

    def test_invalid_outputs_are_rejected(self):
        bad = {
            "not json": "hello world",
            "empty": "",
            "no stages": as_text(good(stages=[])),
            "no profiles": as_text(good(language_profiles=[])),
            "missing objective": as_text(good(stages=[good_stage(1, objective="")])),
            "number not int": as_text(good(stages=[good_stage(1, number="1")])),
            "list of numbers": as_text(good(stages=[good_stage(1, files=[1, 2])])),
            "unknown contract kind": as_text(good(stages=[good_stage(
                1, interface_contract=[{"kind": "magic", "name": "x"}])])),
            "contract without name": as_text(good(stages=[good_stage(
                1, interface_contract=[{"kind": "file", "name": ""}])])),
            "context without reason": as_text(good(context_requested=True,
                                                   context_reason=None)),
            "context not bool": as_text(good(context_requested="yes")),
        }
        for label, text in bad.items():
            with self.subTest(label):
                with self.assertRaises(ManualFormatError):
                    self.parse(text)

    def test_context_request_with_reason_is_kept(self):
        m = self.parse(as_text(good(context_requested=True,
                                    context_reason="need current API docs")))
        self.assertTrue(m.context_requested)
        self.assertEqual(m.context_reason, "need current API docs")


class PromptTest(unittest.TestCase):
    def test_prompt_contains_the_essentials(self):
        p = build_architect_prompt("csv-tool", "Read a CSV", feedback="split stage 1")
        for needle in ("csv-tool", "Read a CSV", "split stage 1", "JSON",
                       "acceptance_criteria", "interface_contract", "secret"):
            self.assertIn(needle, p)

    def test_prompt_without_feedback_has_no_feedback_line(self):
        self.assertNotIn("feedback", build_architect_prompt("n", "o").lower())


class MakeModelArchitectTest(unittest.TestCase):
    def llm(self, answers):
        calls = []
        pending = list(answers)

        def llm_call(prompt):
            calls.append(prompt)
            return pending.pop(0)
        llm_call.calls = calls
        return llm_call

    def test_first_valid_answer_is_used(self):
        llm = self.llm([as_text(good())])
        m = make_model_architect(llm)("csv-tool", "Read a CSV")
        self.assertEqual(len(m.stages), 2)
        self.assertEqual(len(llm.calls), 1)

    def test_one_retry_with_the_error_message(self):
        llm = self.llm(["garbage", as_text(good())])
        m = make_model_architect(llm)("csv-tool", "Read a CSV")
        self.assertEqual(len(m.stages), 2)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("previous answer was invalid", llm.calls[1])

    def test_gives_up_after_two_attempts(self):
        llm = self.llm(["garbage", "still garbage"])
        with self.assertRaises(ManualFormatError):
            make_model_architect(llm)("csv-tool", "Read a CSV")
        self.assertEqual(len(llm.calls), 2)

    def test_feedback_reaches_the_prompt(self):
        llm = self.llm([as_text(good())])
        make_model_architect(llm)("csv-tool", "Read a CSV", "make stages smaller")
        self.assertIn("make stages smaller", llm.calls[0])

    def test_api_errors_are_not_swallowed(self):
        def boom(prompt):
            raise RuntimeError("api down")
        with self.assertRaises(RuntimeError):
            make_model_architect(boom)("n", "o")


class ContractPersistenceTest(unittest.TestCase):
    def test_interface_contract_survives_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            m = parse_manual_json(as_text(good()), "n", "o")
            p = Persistence(d)
            wf = Workflow(project_id="c1", manual=m)
            p.save(wf)
            loaded = p.load("c1")
            self.assertEqual(loaded.manual.stages[0].interface_contract,
                             m.stages[0].interface_contract)
            self.assertEqual(loaded, wf)


if __name__ == "__main__":
    unittest.main()
