from typing import Callable, Optional

from agents.architect import create_master_manual
from agents.evaluator import evaluate_manual
from core.models import EvaluationStatus, Workflow, WorkflowState
from core.persistence import Persistence
from guardrails.topic_filter import TopicResult, classify

S = WorkflowState

# The ONLY legal moves. Anything else raises. No model can skip a state.
ALLOWED_TRANSITIONS = {
    S.IDLE: {S.INTAKE},
    S.INTAKE: {S.ARCHITECTURE, S.IDLE},
    S.ARCHITECTURE: {S.CONTEXT_RESEARCH, S.EVALUATION, S.PAUSED},
    S.CONTEXT_RESEARCH: {S.EVALUATION},
    S.EVALUATION: {S.HUMAN_APPROVAL, S.ARCHITECTURE, S.PAUSED},
    S.HUMAN_APPROVAL: {S.IMPLEMENTATION, S.ARCHITECTURE, S.PAUSED, S.IDLE},
    S.IMPLEMENTATION: {S.PAUSED},
    S.PAUSED: set(),
}

MAX_REVISIONS = 3  # how many times the human may ask for changes
MAX_AUTO_ROUNDS = 2  # automatic architect<->judge rounds before the human gate


class OutOfScopeError(ValueError):
    pass


class IllegalTransition(RuntimeError):
    pass


class ApprovalError(RuntimeError):
    pass


class DesignFailed(RuntimeError):
    pass


class Orchestrator:
    """Deterministic code. It is NOT a language model."""

    def __init__(
        self,
        persistence: Persistence,
        classifier: Callable = classify,
        architect: Callable = create_master_manual,
        evaluator: Callable = evaluate_manual,
    ):
        self.persistence = persistence
        self._classifier = classifier
        self._architect = architect
        self._evaluator = evaluator

    # ---- state machine --------------------------------------------------

    def _go(self, wf: Workflow, new_state: WorkflowState) -> None:
        if new_state not in ALLOWED_TRANSITIONS[wf.state]:
            raise IllegalTransition(f"{wf.state.value} -> {new_state.value}")
        wf.state = new_state
        wf.history.append(new_state.value)
        self.persistence.save(wf)

    # ---- entry ----------------------------------------------------------

    def start_project(self, project_id: str, project_name: str,
                      objective: str) -> Workflow:
        wf = Workflow(project_id=project_id)
        self._go(wf, S.INTAKE)

        try:
            result = self._classifier(objective)
        except Exception:
            result = TopicResult.OTHER  # fail closed

        if result != TopicResult.PROJECT:
            self._go(wf, S.IDLE)
            raise OutOfScopeError(
                "Request rejected: outside software-project scope.")

        self._design(wf, project_name, objective)
        return wf

    def resume(self, project_id: str) -> Workflow:
        return self.persistence.load(project_id)

    # ---- design phase ---------------------------------------------------

    def _design(self, wf: Workflow, project_name: str, objective: str,
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
                corrections = "\n".join(wf.evaluation.corrections)
                feedback = "\n".join(x for x in (human_feedback, corrections) if x)
                continue
            break

        wf.approved = False
        self._go(wf, S.HUMAN_APPROVAL)

    # ---- human gate -----------------------------------------------------

    def _require_gate(self, wf: Workflow) -> None:
        if wf.state != S.HUMAN_APPROVAL:
            raise ApprovalError(f"Not at the human gate (state {wf.state.value}).")

    def approve(self, wf: Workflow) -> None:
        self._require_gate(wf)
        if wf.evaluation is None or wf.evaluation.status != EvaluationStatus.APPROVE:
            raise ApprovalError(
                "The evaluator rejected this manual. Request changes instead.")
        wf.approved = True
        self.persistence.save(wf)

    def request_changes(self, wf: Workflow, feedback: str) -> None:
        self._require_gate(wf)
        try:
            result = self._classifier(feedback)
        except Exception:
            result = TopicResult.OTHER  # fail closed
        if result != TopicResult.PROJECT:
            raise OutOfScopeError("Feedback rejected: outside software-project scope.")
        wf.revision_count += 1
        if wf.revision_count > MAX_REVISIONS:
            self._go(wf, S.PAUSED)
            return
        self._design(wf, wf.manual.project_name, wf.manual.objective, feedback)

    def reject(self, wf: Workflow) -> None:
        self._require_gate(wf)
        self._go(wf, S.IDLE)

    def begin_implementation(self, wf: Workflow) -> None:
        if not wf.approved:
            raise ApprovalError("Implementation requires human approval.")
        self._go(wf, S.IMPLEMENTATION)
