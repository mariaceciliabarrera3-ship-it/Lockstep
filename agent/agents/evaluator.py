"""
Deterministic structural evaluator (first safety belt). It is NOT the
model-based Evaluator; that one will review quality, risk and proportion.
"""
from core.models import Evaluation, EvaluationStatus, MasterManual
from profiles.registry import get_profile


def evaluate_manual(manual: MasterManual) -> Evaluation:
    corrections = []

    if not manual.stages:
        corrections.append("The manual must contain at least one stage.")

    numbers = [s.number for s in manual.stages]
    if numbers != list(range(1, len(numbers) + 1)):
        corrections.append("Stage numbers must be consecutive starting at 1.")

    for name in manual.language_profiles:
        try:
            get_profile(name)
        except ValueError:
            corrections.append(f"Unsupported language profile: {name}")

    for stage in manual.stages:
        if not stage.objective:
            corrections.append(f"Stage {stage.number} has no objective.")
        if not stage.interface_contract:
            corrections.append(f"Stage {stage.number} has no interface contract.")
        if not stage.acceptance_criteria:
            corrections.append(f"Stage {stage.number} has no acceptance criteria.")

    if corrections:
        return Evaluation(EvaluationStatus.REJECT,
                          "Manual requires corrections.", corrections)
    return Evaluation(EvaluationStatus.APPROVE,
                      "Manual passed the structural evaluation.")
