import sys
from jarvis.core.orchestrator import Orchestrator


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("PYTHONPATH=JARVIS_CORE python JARVIS_CORE/jarvis/interfaces/cli.py \"your task\"")
        return

    task = " ".join(sys.argv[1:])

    orchestrator = Orchestrator()
    report = orchestrator.process_task(task)

    print("Jarvis Report")
    print("=" * 40)
    print(f"Task: {report['task']}")
    print(f"Decision: {report['decision']['status']}")
    print(f"Can Apply: {report['decision']['can_apply']}")
    print(f"Reason: {report['decision']['reason']}")
    print("=" * 40)

    for item in report["agent_results"]:
        result = item["result"]
        print(f"Agent: {item['agent']}")
        print(f"Risk: {result.get('risk_level')}")
        print(f"Analysis: {result.get('analysis')}")
        print("-" * 40)


if __name__ == "__main__":
    main()
