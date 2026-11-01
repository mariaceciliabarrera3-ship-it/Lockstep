from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class WorkflowState(str, Enum):
    IDLE = "IDLE"
    INTAKE = "INTAKE"
    ARCHITECTURE = "ARCHITECTURE"
    CONTEXT_RESEARCH = "CONTEXT_RESEARCH"
    EVALUATION = "EVALUATION"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    IMPLEMENTATION = "IMPLEMENTATION"
    PAUSED = "PAUSED"


class EvaluationStatus(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass
class SecretRequirement:
    """A secret a Stage needs. Only the NAME is stored, never the value."""
    name: str
    purpose: str
    source: str


@dataclass
class Stage:
    number: int
    name: str
    objective: str
    requirements: list = field(default_factory=list)
    files: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    acceptance_criteria: list = field(default_factory=list)
    tests: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    interface_contract: list = field(default_factory=list)  # [{kind, name, description}]
    secrets: list = field(default_factory=list)  # list of SecretRequirement


@dataclass
class MasterManual:
    project_name: str
    objective: str
    language_profiles: list
    stages: list  # list of Stage
    context_requested: bool = False
    context_reason: Optional[str] = None
    generated_by: str = "unknown"  # "stub" until a real model is connected


@dataclass
class Evaluation:
    status: EvaluationStatus
    summary: str
    corrections: list = field(default_factory=list)


@dataclass
class Workflow:
    project_id: str
    state: WorkflowState = WorkflowState.IDLE
    manual: Optional[MasterManual] = None
    evaluation: Optional[Evaluation] = None
    approved: bool = False
    revision_count: int = 0
    auto_rounds: int = 0
    history: list = field(default_factory=list)  # states visited, for audit


# ---- rebuilding objects from saved JSON ---------------------------------

def _stage_from_dict(d: dict) -> Stage:
    d = dict(d)
    d["secrets"] = [SecretRequirement(**s) for s in d.get("secrets", [])]
    return Stage(**d)


def _manual_from_dict(d: dict) -> MasterManual:
    d = dict(d)
    d["stages"] = [_stage_from_dict(s) for s in d.get("stages", [])]
    return MasterManual(**d)


def workflow_from_dict(d: dict) -> Workflow:
    manual = d.get("manual")
    evaluation = d.get("evaluation")
    return Workflow(
        project_id=d["project_id"],
        state=WorkflowState(d["state"]),
        manual=_manual_from_dict(manual) if manual else None,
        evaluation=(
            Evaluation(
                status=EvaluationStatus(evaluation["status"]),
                summary=evaluation["summary"],
                corrections=list(evaluation.get("corrections", [])),
            )
            if evaluation
            else None
        ),
        approved=d.get("approved", False),
        revision_count=d.get("revision_count", 0),
        auto_rounds=d.get("auto_rounds", 0),
        history=list(d.get("history", [])),
    )
