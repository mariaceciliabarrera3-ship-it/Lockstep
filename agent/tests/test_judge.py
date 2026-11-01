import json
import unittest

from agents.architect import create_master_manual
from agents.judge import (JudgeFormatError, build_manual_review_prompt,
                          make_model_evaluator, parse_manual_verdict)
from core.models import EvaluationStatus

APPROVE = {"status": "APPROVE", "summary": "Sound and proportionate.", "corrections": []}
REJECT = {"status": "REJECT", "summary": "Problems found.",
          "corrections": ["Stage 1: criteria are not testable; rewrite them as checks"]}


def text(data):
    return json.dumps(data)


class ParseVerdictTest(unittest.TestCase):
    def test_approve(self):
        ev = parse_manual_verdict(text(APPROVE))
        self.assertEqual(ev.status, EvaluationStatus.APPROVE)
        self.assertEqual(ev.corrections, [])

    def test_reject_keeps_the_corrections(self):
        ev = parse_manual_verdict(text(REJECT))
        self.assertEqual(ev.status, EvaluationStatus.REJECT)
        self.assertEqual(ev.corrections, REJECT["corrections"])

    def test_fences_reasoning_and_prose_are_tolerated(self):
        wrapped = "<think>checking {stuff}</think>\nVerdict:\n```json\n" + text(REJECT) + "\n```"
        self.assertEqual(parse_manual_verdict(wrapped).status, EvaluationStatus.REJECT)

    def test_invalid_verdicts_are_rejected(self):
        bad = {
            "not json": "looks fine to me",
            "empty": "",
            "unknown status": text({"status": "MAYBE", "summary": "x", "corrections": []}),
            "lowercase status": text({"status": "approve", "summary": "x", "corrections": []}),
            "reject without corrections": text({"status": "REJECT", "summary": "x", "corrections": []}),
            "approve with corrections": text({"status": "APPROVE", "summary": "x",
                                              "corrections": ["Stage 1: tweak"]}),
            "corrections not strings": text({"status": "REJECT", "summary": "x", "corrections": [1]}),
            "blank correction": text({"status": "REJECT", "summary": "x", "corrections": ["  "]}),
        }
        for label, raw in bad.items():
            with self.subTest(label):
                with self.assertRaises(JudgeFormatError):
                    parse_manual_verdict(raw)


class PromptTest(unittest.TestCase):
    def test_prompt_contains_the_manual_and_the_checklist(self):
        manual = create_master_manual("csv-tool", "Read a CSV and print stats")
        prompt = build_manual_review_prompt(manual)
        for needle in ("Project foundation", "acceptance criteria", "dependenc",
                       "secret", "interface contract", "APPROVE", "REJECT", "JSON"):
            self.assertIn(needle, prompt)


class MakeModelEvaluatorTest(unittest.TestCase):
    def llm(self, answers):
        pending, calls = list(answers), []

        def llm_call(prompt):
            calls.append(prompt)
            return pending.pop(0)
        llm_call.calls = calls
        return llm_call

    def good_manual(self):
        return create_master_manual("n", "python app")

    def test_model_verdict_is_used(self):
        llm = self.llm([text(REJECT)])
        ev = make_model_evaluator(llm)(self.good_manual())
        self.assertEqual(ev.status, EvaluationStatus.REJECT)
        self.assertEqual(len(llm.calls), 1)

    def test_structural_rejection_skips_the_model(self):
        manual = self.good_manual()
        manual.stages = []
        llm = self.llm([text(APPROVE)])
        ev = make_model_evaluator(llm)(manual)
        self.assertEqual(ev.status, EvaluationStatus.REJECT)
        self.assertEqual(llm.calls, [])

    def test_one_retry_on_a_bad_answer(self):
        llm = self.llm(["garbage", text(APPROVE)])
        ev = make_model_evaluator(llm)(self.good_manual())
        self.assertEqual(ev.status, EvaluationStatus.APPROVE)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("previous answer was invalid", llm.calls[1])

    def test_gives_up_after_two_bad_answers(self):
        llm = self.llm(["garbage", "more garbage"])
        with self.assertRaises(JudgeFormatError):
            make_model_evaluator(llm)(self.good_manual())
        self.assertEqual(len(llm.calls), 2)

    def test_api_errors_are_not_swallowed(self):
        def boom(prompt):
            raise RuntimeError("api down")
        with self.assertRaises(RuntimeError):
            make_model_evaluator(boom)(self.good_manual())


if __name__ == "__main__":
    unittest.main()
