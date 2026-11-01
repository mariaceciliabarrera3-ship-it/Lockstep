"""
STUB Architect: returns a fixed one-stage manual. It proves the plumbing,
NOT the quality of any design. Replace with a real model call that returns
the same MasterManual structure.
"""
from typing import Optional

from core.models import MasterManual, Stage


def create_master_manual(project_name: str, objective: str,
                         feedback: Optional[str] = None) -> MasterManual:
    stage_1 = Stage(
        number=1,
        name="Project foundation",
        objective=f"Create the initial structure for: {objective}",
        requirements=[
            "Define project structure",
            "Define dependencies",
            "Define configuration files",
        ],
        files=["README.md", "requirements.txt"],
        acceptance_criteria=[
            "Project structure is documented",
            "Dependencies are declared",
        ],
        tests=["Project starts without errors"],
        interface_contract=[{"kind": "file", "name": "README.md",
                             "description": "project documentation"}],
    )
    return MasterManual(
        project_name=project_name,
        objective=objective,
        language_profiles=["python"],
        stages=[stage_1],
        context_requested=False,
        generated_by="stub",
    )
