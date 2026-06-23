from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agents.root_cause_agent import RootCauseAgent


def main():

    agent = RootCauseAgent()

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

    print("\n" + "=" * 80)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 80)

    analysis = agent.analyze(
        incident
    )

    print(analysis)


if __name__ == "__main__":
    main()