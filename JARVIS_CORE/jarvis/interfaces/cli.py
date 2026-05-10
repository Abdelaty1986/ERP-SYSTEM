import sys

from jarvis.core.orchestrator import Orchestrator
from jarvis.core.output_formatter import OutputFormatter


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("PYTHONPATH=JARVIS_CORE python JARVIS_CORE/jarvis/interfaces/cli.py \"your task\"")
        return

    task = " ".join(sys.argv[1:])

    orchestrator = Orchestrator()
    formatter = OutputFormatter()

    report = orchestrator.process_task(task)

    print(formatter.format_report(report))


if __name__ == "__main__":
    main()
