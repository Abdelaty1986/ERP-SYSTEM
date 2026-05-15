import json

from jarvis.runtime.execution_state_machine import ExecutionStateMachine
from jarvis.runtime.execution_explainer import ExecutionExplainer
from jarvis.runtime.execution_history_runtime import ExecutionHistoryRuntime
from jarvis.runtime.execution_console_runtime import ExecutionConsoleRuntime
from jarvis.runtime.execution_approval_runtime import ExecutionApprovalRuntime
from jarvis.runtime.execution_timeline_runtime import ExecutionTimelineRuntime


def build_report():
    command = "probe explainable execution runtime"

    machine = ExecutionStateMachine()
    explainer = ExecutionExplainer()
    history = ExecutionHistoryRuntime()
    console = ExecutionConsoleRuntime()
    approval = ExecutionApprovalRuntime()
    timeline_runtime = ExecutionTimelineRuntime()

    timeline = machine.build(command)
    explanation = explainer.explain(command)
    approval_state = approval.set_waiting(command)

    record = history.append(
        {
            "command": command,
            "timeline": timeline,
            "explanation": explanation,
            "approval": approval_state,
        }
    )

    console_state = console.write_state(
        {
            "current_task": command,
            "execution_status": "WAITING_APPROVAL",
            "approval_state": approval_state,
        }
    )

    timeline_event = timeline_runtime.append_event(
        {
            "event": "EXPLAINABLE_EXECUTION_PROBE",
            "command": command,
            "status": "ok",
        }
    )

    return {
        "ok": True,
        "runtime": "explainable_execution_runtime",
        "bounded": True,
        "execution_mode": "approval_driven_execution",
        "dangerous_execution": False,
        "record": record,
        "console_state": console_state,
        "timeline_event": timeline_event,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2, ensure_ascii=False))
