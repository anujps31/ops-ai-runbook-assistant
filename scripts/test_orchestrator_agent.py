from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agents.orchestrator_agent import OrchestratorAgent


def main():

    incident = """
Production API returning 503 errors.

Symptoms:
- Customers unable to login
- Increased latency
- Multiple pods restarting
"""

    print("=" * 80)
    print("INCIDENT")
    print("=" * 80)
    print(incident)

    agent = OrchestratorAgent()

    result = agent.analyze(
        incident=incident
    )

    print("\n" + "=" * 80)
    print("INCIDENT ANALYSIS")
    print("=" * 80)

    print(
        result.get(
            "incident_analysis",
            "No analysis generated"
        )
    )

    print("\n" + "=" * 80)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 80)

    print(
        result.get(
            "root_cause",
            "No root cause generated"
        )
    )

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    print(
        result.get(
            "recommendations",
            "No recommendations generated"
        )
    )

    print("\n" + "=" * 80)
    print("ORCHESTRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()