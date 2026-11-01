"""Measure the judge on the calibration set (needs config.json and NEBIUS_API_KEY).
    PYTHONPATH=. python3 scripts/eval_judge.py
Prints expected vs obtained per case, accuracy, FALSE APPROVALS (a flawed manual
approved: the worst error) and FALSE REJECTIONS. Never prints the key."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.architect_llm import parse_manual_json  # noqa: E402
from agents.judge import make_model_evaluator  # noqa: E402
from core.config import load_config  # noqa: E402
from core.llm import NebiusClient, make_llm_call  # noqa: E402


def main():
    cfg = load_config("config.json")
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        sys.exit("NEBIUS_API_KEY is not set")
    client = NebiusClient(cfg["nebius"]["base_url"], key)
    judge = make_model_evaluator(make_llm_call(client, cfg["models"]["judge"], max_tokens=2048))
    with open("data/manual_calibration.json", encoding="utf-8") as f:
        cases = json.load(f)
    right, false_approvals, false_rejections = 0, [], []
    for case in cases:
        manual = parse_manual_json(json.dumps(case["manual"]), "calibration", "calibration")
        try:
            got = judge(manual).status.value
        except Exception as exc:  # one bad answer must not stop the run
            got = f"ERROR({type(exc).__name__})"
        ok = got == case["expected"]
        right += ok
        print(f"{'OK ' if ok else 'BAD'} {case['name']}: expected {case['expected']}, got {got}")
        if not ok and case["expected"] == "REJECT" and got == "APPROVE":
            false_approvals.append(case["name"])
        if not ok and case["expected"] == "APPROVE" and got == "REJECT":
            false_rejections.append(case["name"])
    print(f"\nAccuracy: {right}/{len(cases)}")
    print("FALSE APPROVALS (flawed manual approved):", false_approvals or "none")
    print("FALSE REJECTIONS (sound manual rejected):", false_rejections or "none")


if __name__ == "__main__":
    main()
