import json
import os
import re
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .models import Workflow, workflow_from_dict

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _clean(obj, redact: Optional[Callable[[str], str]]):
    """Turn Enums into plain values and redact every string before saving."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _clean(v, redact) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v, redact) for v in obj]
    if isinstance(obj, str) and redact:
        return redact(obj)
    return obj


class Persistence:
    def __init__(self, directory: str = "state",
                 redact: Optional[Callable[[str], str]] = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._redact = redact

    def _path(self, project_id: str) -> Path:
        if not _SAFE_ID.match(project_id):
            raise ValueError(f"Unsafe project id: {project_id!r}")
        return self.directory / f"{project_id}.json"

    def save(self, workflow: Workflow) -> None:
        data = _clean(asdict(workflow), self._redact)
        path = self._path(workflow.project_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        os.replace(tmp, path)  # atomic: a crash never leaves a half file

    def load(self, project_id: str) -> Workflow:
        path = self._path(project_id)
        if not path.exists():
            raise FileNotFoundError(f"No saved project: {project_id}")
        return workflow_from_dict(json.loads(path.read_text(encoding="utf-8")))
