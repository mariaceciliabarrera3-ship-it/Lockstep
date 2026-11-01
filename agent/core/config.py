import json


class ConfigError(Exception):
    pass


REQUIRED_ROLES = ("classifier", "architect", "judge")
AUTHOR_REVIEWER_PAIRS = (("architect", "judge"), ("programmer", "judge"))


def check_independence(config: dict) -> None:
    models = config.get("models", {})
    for author, reviewer in AUTHOR_REVIEWER_PAIRS:
        if author in models and reviewer in models and models[author] == models[reviewer]:
            raise ConfigError(
                f"Author role '{author}' and reviewer role '{reviewer}' use the same model")


def load_config(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config: {exc}")
    if not data.get("nebius", {}).get("base_url"):
        raise ConfigError("Missing nebius.base_url")
    models = data.get("models", {})
    for role in REQUIRED_ROLES:
        if not models.get(role):
            raise ConfigError(f"Missing model for role: {role}")
    for role, model_id in models.items():
        if str(model_id).upper().startswith("FILL"):
            raise ConfigError(f"Model for role '{role}' is still a placeholder")
    check_independence(data)
    return data
