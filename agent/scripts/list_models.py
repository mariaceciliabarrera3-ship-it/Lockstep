import os
import sys
import json
import urllib.request
from core.config import load_config

def main():
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        print("Error: NEBIUS_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config("config.json")
    except Exception:
        # Fallback si config.json tiene placeholders
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

    base_url = config.get("nebius", {}).get("base_url", "https://api.tokenfactory.nebius.com/v1/").rstrip("/") + "/"
    url = f"{base_url}models"

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m["id"] for m in data.get("data", []) if "nemotron" in m.get("id", "").lower()]
            for m in models:
                print(m)
    except Exception as e:
        err_msg = str(e).replace(api_key, "[REDACTED]")
        print(f"Error fetching models: {err_msg}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()