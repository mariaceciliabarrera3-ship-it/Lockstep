"""Run the real Architect, then the real Programmer on Stage 1, in a fresh git workspace.
    PYTHONPATH=. python3 scripts/try_programmer.py "A command line tool that counts words in a file"
Needs config.json and NEBIUS_API_KEY. Never prints the key. Output goes to workspaces/ (git-ignored)."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.architect_llm import make_model_architect  # noqa: E402
from agents.programmer import make_model_programmer  # noqa: E402
from core.config import load_config  # noqa: E402
from core.llm import NebiusClient, make_llm_call  # noqa: E402
from sandbox.workspace import Workspace  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python3 scripts/try_programmer.py "<project objective>"')
    cfg = load_config("config.json")
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        sys.exit("NEBIUS_API_KEY is not set")
    client = NebiusClient(cfg["nebius"]["base_url"], key)
    models = cfg["models"]
    architect = make_model_architect(make_llm_call(client, models["architect"], max_tokens=4096))
    programmer_model = models.get("programmer", models["architect"])
    programmer = make_model_programmer(make_llm_call(client, programmer_model, max_tokens=8192))

    objective = " ".join(sys.argv[1:])
    manual = architect("try-programmer", objective)
    stage = manual.stages[0]
    print(f"Stage {stage.number}: {stage.name}\n  Files allowed: {stage.files}")

    root = os.path.join("workspaces", "try-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    ws = Workspace(root)
    ws.init()
    result = programmer(stage, ws)
    print("\nFiles written:", result.written)
    print("Notes:", result.notes)
    print("Outside the allowed scope:", ws.check_scope(stage.files) or "nothing")
    print("\n----- DIFF -----")
    print(ws.diff())
    print("Committed as:", ws.commit_stage(stage.number, stage.name))
    print(f"Project folder: {root}")


if __name__ == "__main__":
    main()
