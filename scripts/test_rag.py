from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.rag_service import RAGService


def main():

    rag = RAGService()

    questions = [
        "What should I do if API returns 503 errors?",
        "How do I troubleshoot CrashLoopBackOff?",
        "What are the steps in P1 incident response?"
    ]

    for question in questions:

        print("\n" + "=" * 80)
        print("QUESTION:")
        print(question)

        answer = rag.ask(question)

        print("\nANSWER:")
        print(answer)


if __name__ == "__main__":
    main()