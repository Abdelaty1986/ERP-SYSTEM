import json

from jarvis.runtime.confidence_decay_runtime import ConfidenceDecayRuntime


def build_report():
    return ConfidenceDecayRuntime().apply_decay()


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2))
