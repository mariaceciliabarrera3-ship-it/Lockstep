import json
import os
from dataclasses import dataclass

from agents.architect_llm import ManualFormatError, _extract_json
from sandbox.workspace import path_allowed


class ProgrammerFormatError(ValueError):
    pass


class ScopeViolation(RuntimeError):
    def __init__(self, paths):
        super().__init__("Change outside the stage scope: " + ", ".join(paths))
        self.paths = list(paths)


@dataclass
class ApplyResult:
    written: list
    notes: str = ""


PROGRAMMER_PROMPT = """You are the Programmer. Implement ONLY the Stage below, touching only its
allowed files. Prefer small edits to existing files over rewriting them.
Reply with ONLY one JSON object:
{"files": [
  {"path": "relative/path.py", "content": "full new file content"},
  {"path": "other.py", "edits": [{"search": "exact existing text", "replace": "new text"}]}
 ],
 "notes": "one or two sentences"}
Rules: use "content" for a new file, "edits" (search/replace, each search text must
appear exactly once) for an existing file. Never write outside the allowed files.
Never put secret values in code: read them from environment variables by name.
Follow the interface contract exactly (names, signatures, CLI arguments).

STAGE <<NUMBER>>: <<NAME>>
Objective: <<OBJECTIVE>>
Requirements:
<<REQUIREMENTS>>
Acceptance criteria:
<<CRITERIA>>
Interface contract:
<<CONTRACT>>
Allowed files:
<<ALLOWED>>
<<FEEDBACK>>
CURRENT CONTENT OF EXISTING ALLOWED FILES:
<<EXISTING>>"""


def _bullets(items):
    return "\n".join(f"- {i}" for i in items) or "- (none)"


def build_programmer_prompt(stage, existing, feedback=None):
    contract = _bullets(f"[{c.get('kind')}] {c.get('name')} - {c.get('description', '')}"
                        for c in stage.interface_contract)
    existing_text = "\n".join(f"--- {path} ---\n{content}" for path, content in existing.items()) \
        or "(no files yet)"
    fb = f"Feedback to address:\n{feedback}\n" if feedback else ""
    return (PROGRAMMER_PROMPT.replace("<<NUMBER>>", str(stage.number))
            .replace("<<NAME>>", stage.name).replace("<<OBJECTIVE>>", stage.objective)
            .replace("<<REQUIREMENTS>>", _bullets(stage.requirements))
            .replace("<<CRITERIA>>", _bullets(stage.acceptance_criteria))
            .replace("<<CONTRACT>>", contract).replace("<<ALLOWED>>", _bullets(stage.files))
            .replace("<<FEEDBACK>>", fb).replace("<<EXISTING>>", existing_text))


def parse_programmer_output(text):
    try:
        data = _extract_json(text)
    except ManualFormatError as exc:
        raise ProgrammerFormatError(str(exc))
    if not isinstance(data, dict):
        raise ProgrammerFormatError("top level must be an object")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise ProgrammerFormatError("'files' must be a non-empty list")
    changes = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ProgrammerFormatError("each file entry must be an object")
        path = entry.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ProgrammerFormatError("each file needs a non-empty 'path'")
        has_content, has_edits = "content" in entry, "edits" in entry
        if has_content == has_edits:
            raise ProgrammerFormatError(f"{path}: give exactly one of 'content' or 'edits'")
        if has_content:
            if not isinstance(entry["content"], str):
                raise ProgrammerFormatError(f"{path}: 'content' must be a string")
            changes.append({"path": path, "content": entry["content"]})
        else:
            edits = entry["edits"]
            if not isinstance(edits, list) or not edits:
                raise ProgrammerFormatError(f"{path}: 'edits' must be a non-empty list")
            for e in edits:
                if (not isinstance(e, dict) or not isinstance(e.get("search"), str)
                        or not e["search"] or not isinstance(e.get("replace"), str)):
                    raise ProgrammerFormatError(
                        f"{path}: every edit needs a non-empty 'search' and a 'replace' string")
            changes.append({"path": path, "edits": edits})
    notes = data.get("notes", "")
    return changes, notes if isinstance(notes, str) else ""


def _norm(path):
    return os.path.normpath(path).replace("\\", "/")


def apply_changes(workspace, changes, allowed_files, notes=""):
    # 1) compute every final content first: any problem stops before writing anything
    finals = {}
    for change in changes:
        path = _norm(change["path"])
        if "content" in change:
            finals[path] = change["content"]
            continue
        try:
            current = finals[path] if path in finals else workspace.read_file(path)
        except FileNotFoundError:
            raise ProgrammerFormatError(f"{path}: cannot edit a file that does not exist")
        for edit in change["edits"]:
            count = current.count(edit["search"])
            if count != 1:
                raise ProgrammerFormatError(
                    f"{path}: the text to replace must appear exactly once (found {count})")
            current = current.replace(edit["search"], edit["replace"], 1)
        finals[path] = current
    # 2) scope check before any write
    outside = sorted(p for p in finals if not path_allowed(p, allowed_files))
    if outside:
        raise ScopeViolation(outside)
    # 3) write
    for path, content in finals.items():
        workspace.write_file(path, content)
    leftover = workspace.check_scope(allowed_files)
    if leftover:
        raise ScopeViolation(leftover)
    return ApplyResult(written=sorted(finals), notes=notes)


def make_model_programmer(llm_call):
    def programmer(stage, workspace, feedback=None):
        existing = {}
        for path in stage.files:
            if path.endswith("/"):
                continue
            try:
                existing[path] = workspace.read_file(path)
            except FileNotFoundError:
                pass
        prompt = build_programmer_prompt(stage, existing, feedback)
        last_error = None
        for _ in range(2):
            p = prompt if last_error is None else (
                prompt + f"\n\nYour previous answer was invalid: {last_error}\n"
                         "Return ONLY the corrected JSON object.")
            try:
                changes, notes = parse_programmer_output(llm_call(p))
                return apply_changes(workspace, changes, stage.files, notes)
            except ProgrammerFormatError as exc:
                last_error = str(exc)
        raise ProgrammerFormatError(f"Programmer output invalid after 2 attempts: {last_error}")
    return programmer
