from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agents.recommendation_agent import RecommendationAgent


def main():

    incident = """
AKS application pods are restarting continuously.

Symptoms:
- Multiple pod restarts
- CrashLoopBackOff observed
- Users reporting intermittent failures
"""

    print("=" * 80)
    print("INCIDENT")
    print("=" * 80)
    print(incident)

    print("\n" + "=" * 80)
    print("RECOMMENDED ACTIONS")
    print("=" * 80)

    agent = RecommendationAgent()

    recommendations = agent.recommend(
        incident=incident
    )

    print(recommendations)

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()