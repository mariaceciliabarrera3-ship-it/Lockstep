from core.models import EvaluationStatus


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
    return "\n".join(lines)
