import json
from dataclasses import asdict

from agents.architect_llm import ManualFormatError, _extract_json
from agents.evaluator import evaluate_manual
from core.models import Evaluation, EvaluationStatus


class JudgeFormatError(ValueError):
    pass


JUDGE_PROMPT = """You are the independent reviewer (judge) of a Master Development Manual
written by another model. Review it with evidence, not taste. Check:
1. Every acceptance criterion can be verified by a test (no vague wording).
2. Stages are in a valid order and dependencies point only to earlier stages.
3. Proportionality: nothing heavier than the stated goal needs.
4. Security: secrets are names only and never stored in the repo; no unsafe
   practices such as eval() on external input.
5. The interface contract (files, functions, CLI) is consistent with the
   acceptance criteria and the files of the same stage.
6. Scope: each stage does only what its objective says.
Reply with ONLY one JSON object:
{"status": "APPROVE" or "REJECT", "summary": "one or two sentences",
 "corrections": ["Stage N: what is wrong and exactly what to change"]}
Use REJECT only if you found a concrete problem; then give at least one
correction naming the stage. With APPROVE the corrections list must be empty.

MANUAL (JSON):
<<MANUAL>>"""


def build_manual_review_prompt(manual):
    return JUDGE_PROMPT.replace("<<MANUAL>>", json.dumps(asdict(manual), ensure_ascii=False, indent=1))


def parse_manual_verdict(text):
    try:
        data = _extract_json(text)
    except ManualFormatError as exc:
        raise JudgeFormatError(str(exc))
    if not isinstance(data, dict):
        raise JudgeFormatError("top level must be an object")
    status = data.get("status")
    if status not in ("APPROVE", "REJECT"):
        raise JudgeFormatError("'status' must be exactly APPROVE or REJECT")
    summary = data.get("summary", "")
    if not isinstance(summary, str):
        raise JudgeFormatError("'summary' must be a string")
    corrections = data.get("corrections", [])
    if not isinstance(corrections, list) or not all(isinstance(c, str) and c.strip() for c in corrections):
        raise JudgeFormatError("'corrections' must be a list of non-empty strings")
    if status == "REJECT" and not corrections:
        raise JudgeFormatError("REJECT requires at least one correction")
    if status == "APPROVE" and corrections:
        raise JudgeFormatError("APPROVE must not include corrections")
    return Evaluation(EvaluationStatus(status), summary, corrections)


def make_model_evaluator(llm_call):
    def evaluator(manual):
        structural = evaluate_manual(manual)
        if structural.status == EvaluationStatus.REJECT:
            return structural  # deterministic check first: no tokens spent
        prompt = build_manual_review_prompt(manual)
        last_error = None
        for _ in range(2):
            p = prompt if last_error is None else (
                prompt + f"\n\nYour previous answer was invalid: {last_error}\n"
                         "Return ONLY the corrected JSON object.")
            try:
                return parse_manual_verdict(llm_call(p))
            except JudgeFormatError as exc:
                last_error = str(exc)
        raise JudgeFormatError(f"Judge output invalid after 2 attempts: {last_error}")
    return evaluator
