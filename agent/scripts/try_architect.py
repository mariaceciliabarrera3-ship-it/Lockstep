"""Ask the real Architect model for a Master Manual. Usage:
    PYTHONPATH=. python3 scripts/try_architect.py "Build a web page for an ice cream shop"
Needs config.json and NEBIUS_API_KEY. Never prints the key."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.architect_llm import make_model_architect  # noqa: E402
from core.config import load_config  # noqa: E402
from core.llm import NebiusClient, make_llm_call  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python3 scripts/try_architect.py "<project objective>"')
    cfg = load_config("config.json")
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        sys.exit("NEBIUS_API_KEY is not set")
    client = NebiusClient(cfg["nebius"]["base_url"], key)
    architect = make_model_architect(
        make_llm_call(client, cfg["models"]["architect"], max_tokens=4096))
    manual = architect("try-architect", " ".join(sys.argv[1:]))
    print(f"Languages: {manual.language_profiles}  Context requested: {manual.context_requested}")
    for st in manual.stages:
        print(f"\nStage {st.number}: {st.name}\n  Objective: {st.objective}")
        for c in st.acceptance_criteria:
            print(f"  Criterion: {c}")
        for item in st.interface_contract:
            print(f"  Contract: [{item['kind']}] {item['name']} - {item.get('description', '')}")
        for sec in st.secrets:
            print(f"  Secret (name only): {sec.name}")


if __name__ == "__main__":
    main()
