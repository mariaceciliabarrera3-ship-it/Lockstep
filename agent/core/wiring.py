from collections import namedtuple

from agents.architect_llm import make_model_architect
from agents.judge import make_model_evaluator
from core.config import ConfigError, load_config
from core.llm import NebiusClient, make_llm_call
from core.orchestrator import Orchestrator
from core.persistence import Persistence
from guardrails.topic_filter import make_model_classifier

Wiring = namedtuple("Wiring", "orchestrator mode reason")


def build_orchestrator(config_path, environ, state_dir="state", redact=None):
    persistence = Persistence(state_dir, redact=redact)
    try:
        cfg = load_config(config_path)
        key = environ.get("NEBIUS_API_KEY")
        if not key:
            raise ConfigError("NEBIUS_API_KEY is not set")
    except ConfigError as exc:
        return Wiring(Orchestrator(persistence), "OFFLINE", str(exc))
    client = NebiusClient(cfg["nebius"]["base_url"], key)
    classifier = make_model_classifier(client, cfg["models"]["classifier"],
                                       extra=cfg.get("classifier_extra"))
    architect = make_model_architect(
        make_llm_call(client, cfg["models"]["architect"], max_tokens=4096))
    evaluator = make_model_evaluator(
        make_llm_call(client, cfg["models"]["judge"], max_tokens=2048))
    return Wiring(Orchestrator(persistence, classifier=classifier, architect=architect,
                               evaluator=evaluator),
                  "ONLINE", "")
