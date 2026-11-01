"""
Apply the minimal B2 patches to the project (run from the agent/ folder):
    python3 apply_b2_patch.py
- core/models.py: adds Workflow.auto_rounds (only if missing).
- core/orchestrator.py: adds MAX_AUTO_ROUNDS, the EVALUATION transitions and the
  new _design method with the automatic improvement rounds (only if missing).
- core/report.py: creates gate_report(wf) (only if the file does not exist).
Every file it changes is first copied to backup_before_b2_patch/.
It never touches tests, config.json, scripts/ or anything else.
"""
import os
import shutil
import sys

BACKUP = "backup_before_b2_patch"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def backup(path):
    os.makedirs(os.path.join(BACKUP, os.path.dirname(path)), exist_ok=True)
    shutil.copy2(path, os.path.join(BACKUP, path))


def patch_models():
    path = "core/models.py"
    s = read(path)
    if "auto_rounds" in s:
        print("models.py: already has auto_rounds (skipped)")
        return
    a = "    revision_count: int = 0\n"
    b = '        revision_count=d.get("revision_count", 0),'
    if a not in s or b not in s:
        sys.exit("models.py: unexpected content. Restore B1c first (restore_bundle.py).")
    backup(path)
    s = s.replace(a, a + "    auto_rounds: int = 0\n", 1)
    s = s.replace(b, b + '\n        auto_rounds=d.get("auto_rounds", 0),')
    write(path, s)
    print("models.py: patched")


NEW_DESIGN = '''    def _design(self, wf: Workflow, project_name: str, objective: str,
                feedback: Optional[str] = None) -> None:
        human_feedback = feedback
        wf.auto_rounds = 0
        while True:
            self._go(wf, S.ARCHITECTURE)
            try:
                manual = self._architect(project_name, objective, feedback)
            except Exception as exc:
                self._go(wf, S.PAUSED)
                raise DesignFailed(str(exc)) from exc
            wf.manual = manual

            if manual.context_requested:
                self._go(wf, S.CONTEXT_RESEARCH)
                # Tavily plugs in here later (max 5 searches / 2 extracts).

            self._go(wf, S.EVALUATION)
            try:
                wf.evaluation = self._evaluator(manual)
            except Exception as exc:
                self._go(wf, S.PAUSED)
                raise DesignFailed(str(exc)) from exc

            if (wf.evaluation.status == EvaluationStatus.REJECT
                    and wf.auto_rounds < MAX_AUTO_ROUNDS):
                wf.auto_rounds += 1
                corrections = "\\n".join(wf.evaluation.corrections)
                feedback = "\\n".join(x for x in (human_feedback, corrections) if x)
                continue
            break

        wf.approved = False
        self._go(wf, S.HUMAN_APPROVAL)

'''


def patch_orchestrator():
    path = "core/orchestrator.py"
    s = read(path)
    if "MAX_AUTO_ROUNDS" in s:
        print("orchestrator.py: already patched (skipped)")
        return
    anchor1 = "MAX_REVISIONS = 3"
    anchor2 = "S.EVALUATION: {S.HUMAN_APPROVAL},"
    anchor3 = "    def _design("
    anchor4 = "    # ---- human gate"
    for a in (anchor1, anchor2, anchor3, anchor4):
        if a not in s:
            sys.exit(f"orchestrator.py: missing '{a}'. Restore B1c first (restore_bundle.py).")
    backup(path)
    line_end = s.index("\n", s.index(anchor1))
    s = (s[:line_end] + "\nMAX_AUTO_ROUNDS = 2  # automatic architect<->judge rounds before the human gate"
         + s[line_end:])
    s = s.replace(anchor2, "S.EVALUATION: {S.HUMAN_APPROVAL, S.ARCHITECTURE, S.PAUSED},", 1)
    start, end = s.index(anchor3), s.index(anchor4)
    s = s[:start] + NEW_DESIGN + s[end:]
    write(path, s)
    print("orchestrator.py: patched")


REPORT = '''from core.models import EvaluationStatus


def gate_report(wf):
    m = wf.manual
    if m is None:
        return "No manual has been produced yet."
    lines = [f"PROJECT: {m.project_name}", f"Goal: {m.objective}",
             f"Written by: {m.generated_by}", f"Stages: {len(m.stages)}"]
    for st in m.stages:
        lines.append(f"  Stage {st.number}: {st.name} - {st.objective}")
        for c in st.acceptance_criteria:
            lines.append(f"    How to check: {c}")
    ev = wf.evaluation
    if ev is not None:
        lines.append(f"Reviewer verdict: {ev.status.value} - {ev.summary}")
        for c in ev.corrections:
            lines.append(f"  Needs fixing: {c}")
    lines.append(f"Automatic improvement rounds used: {wf.auto_rounds} of 2")
    if ev is not None and ev.status == EvaluationStatus.REJECT:
        lines.append("You cannot approve this manual: the reviewer rejected it. "
                     "Ask for changes or reject it.")
    else:
        lines.append("Nothing is implemented until you approve.")
    return "\\n".join(lines)
'''


def create_report():
    path = "core/report.py"
    if os.path.exists(path):
        print("report.py: already exists (kept)")
        return
    write(path, REPORT)
    print("report.py: created")


def main():
    if not (os.path.isdir("core") and os.path.isdir("tests")):
        sys.exit("Run this from the agent/ folder (it must contain core/ and tests/).")
    patch_models()
    patch_orchestrator()
    create_report()
    print("Done. Now run: python3 -m unittest discover -s tests -t . 2>&1 | tail -15")


if __name__ == "__main__":
    main()