import csv
import json
import os
import sys

from core.config import load_config
from core.llm import NebiusClient
from guardrails.topic_filter import TopicResult, make_model_classifier


def main():
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        print("Error: NEBIUS_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config("config.json")
    except Exception:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

    base_url = config.get("nebius", {}).get("base_url", "https://api.tokenfactory.nebius.com/v1/")
    model = config.get("models", {}).get("classifier", "FILL")
    extra = config.get("classifier_extra", None)

    client = NebiusClient(base_url, api_key)
    classifier = make_model_classifier(client, model, extra=extra)

    correct = 0
    total = 0
    false_positives = []  # OTHER -> PROJECT
    false_negatives = []  # PROJECT -> OTHER

    with open("data/classifier_eval.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            expected = row["label"].strip()
            message = row["message"].strip()
            total += 1

            result = classifier(message)
            actual = "PROJECT" if result == TopicResult.PROJECT else "OTHER"

            if actual == expected:
                correct += 1
            else:
                if expected == "OTHER" and actual == "PROJECT":
                    false_positives.append(message)
                elif expected == "PROJECT" and actual == "OTHER":
                    false_negatives.append(message)

    accuracy = (correct / total) * 100 if total > 0 else 0
    print(f"Accuracy: {accuracy:.2f}% ({correct}/{total})")
    print(f"False Positives (OTHER as PROJECT): {false_positives}")
    print(f"False Negatives (PROJECT as OTHER): {false_negatives}")


if __name__ == "__main__":
    main()