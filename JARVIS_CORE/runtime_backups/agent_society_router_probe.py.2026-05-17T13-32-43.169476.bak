import json
from jarvis.runtime.agent_society_router import AgentSocietyRouter


if __name__ == "__main__":
    router = AgentSocietyRouter()
    samples = [
        "plan next engineering layer",
        "implement patch safely",
        "validate compile checks",
        "rollback failed mutation",
        "review code quality",
        "record learning memory",
        "check security risk"
    ]

    results = [router.route(task) for task in samples]

    print(json.dumps({
        "runtime": "agent_society_router_probe",
        "bounded": True,
        "sample_count": len(results),
        "routes": [
            {
                "task": r["task"],
                "selected_agent": r["selected_agent"],
                "execution_allowed": r["execution_allowed"],
                "approval_required": r["approval_required"]
            }
            for r in results
        ]
    }, ensure_ascii=False, indent=2))
