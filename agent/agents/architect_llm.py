import json
import re

from core.models import MasterManual, SecretRequirement, Stage


class ManualFormatError(ValueError):
    pass


LIST_FIELDS = ("requirements", "files", "dependencies", "inputs", "outputs",
               "acceptance_criteria", "tests", "risks")
CONTRACT_KINDS = {"function", "class", "cli", "endpoint", "file", "format"}

ARCHITECT_PROMPT = """You are the Architect of a staged software-development agent.
Turn the project request into a Master Development Manual split into small Stages.
Each Stage must be small enough to implement, run, verify and revert on its own.

Project name: <<PROJECT_NAME>>
Project request: <<OBJECTIVE>>
<<FEEDBACK>>
Reply with ONLY one JSON object, no prose, with exactly this shape:
{"language_profiles": ["python"],
 "context_requested": false, "context_reason": null,
 "stages": [{"number": 1, "name": "...", "objective": "...",
   "requirements": ["..."], "files": ["..."], "dependencies": ["..."],
   "inputs": ["..."], "outputs": ["..."], "acceptance_criteria": ["..."],
   "tests": ["..."], "risks": ["..."],
   "interface_contract": [{"kind": "function|class|cli|endpoint|file|format",
                           "name": "...", "description": "..."}],
   "secrets": [{"name": "ENV_VAR_NAME", "purpose": "...", "source": "..."}]}]}
Rules: every Stage needs acceptance_criteria and an interface_contract (exact
file paths, function names and signatures, CLI arguments or endpoints) so tests
can check behavior. Never include secret values, only variable names. Set
context_requested to true only if external documentation is truly needed, and
then give context_reason."""


def build_architect_prompt(project_name, objective, feedback=None):
    fb = f"Reviewer feedback to address: {feedback}\n" if feedback else ""
    return (ARCHITECT_PROMPT.replace("<<PROJECT_NAME>>", project_name)
            .replace("<<OBJECTIVE>>", objective).replace("<<FEEDBACK>>", fb))


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _extract_json(text):
    if not text:
        raise ManualFormatError("empty answer")
    t = _THINK.sub("", text)
    if "</think>" in t.lower():
        t = t[t.lower().rfind("</think>") + len("</think>"):]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ManualFormatError("no JSON object found")
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ManualFormatError(f"invalid JSON: {exc}")


def _str_list(n, d, key):
    v = d.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ManualFormatError(f"stage {n}: '{key}' must be a list of strings")
    return v


def _stage(d):
    if not isinstance(d, dict):
        raise ManualFormatError("each stage must be an object")
    n = d.get("number")
    if not isinstance(n, int) or isinstance(n, bool):
        raise ManualFormatError("stage 'number' must be an integer")
    for key in ("name", "objective"):
        if not isinstance(d.get(key), str) or not d[key].strip():
            raise ManualFormatError(f"stage {n}: '{key}' is required")
    lists = {k: _str_list(n, d, k) for k in LIST_FIELDS}
    contract = d.get("interface_contract", [])
    if not isinstance(contract, list):
        raise ManualFormatError(f"stage {n}: 'interface_contract' must be a list")
    for c in contract:
        if (not isinstance(c, dict) or c.get("kind") not in CONTRACT_KINDS
                or not isinstance(c.get("name"), str) or not c["name"].strip()):
            raise ManualFormatError(
                f"stage {n}: bad interface_contract entry (kind must be one of "
                f"{sorted(CONTRACT_KINDS)} and name is required)")
    secrets = []
    for sec in d.get("secrets", []):
        if not isinstance(sec, dict) or not isinstance(sec.get("name"), str) or not sec["name"]:
            raise ManualFormatError(f"stage {n}: bad secret entry")
        if "value" in sec:
            raise ManualFormatError(f"stage {n}: secrets must never include a value")
        secrets.append(SecretRequirement(sec["name"], str(sec.get("purpose", "")),
                                         str(sec.get("source", ""))))
    return Stage(number=n, name=d["name"], objective=d["objective"],
                 interface_contract=contract, secrets=secrets, **lists)


def parse_manual_json(text, project_name, objective):
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise ManualFormatError("top level must be an object")
    stages = data.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ManualFormatError("'stages' must be a non-empty list")
    profiles = data.get("language_profiles")
    if (not isinstance(profiles, list) or not profiles
            or not all(isinstance(p, str) for p in profiles)):
        raise ManualFormatError("'language_profiles' must be a non-empty list of strings")
    wants = data.get("context_requested", False)
    if not isinstance(wants, bool):
        raise ManualFormatError("'context_requested' must be true or false")
    reason = data.get("context_reason")
    if wants and not (isinstance(reason, str) and reason.strip()):
        raise ManualFormatError("'context_reason' is required when context_requested is true")
    return MasterManual(project_name=project_name, objective=objective,
                        language_profiles=profiles,
                        stages=[_stage(s) for s in stages],
                        context_requested=wants, context_reason=reason if wants else None,
                        generated_by="model")


def make_model_architect(llm_call):
    def architect(project_name, objective, feedback=None):
        prompt = build_architect_prompt(project_name, objective, feedback)
        last_error = None
        for _ in range(2):
            p = prompt if last_error is None else (
                prompt + f"\n\nYour previous answer was invalid: {last_error}\n"
                         "Return ONLY the corrected JSON object.")
            try:
                return parse_manual_json(llm_call(p), project_name, objective)
            except ManualFormatError as exc:
                last_error = str(exc)
        raise ManualFormatError(f"Architect output invalid after 2 attempts: {last_error}")
    return architect
