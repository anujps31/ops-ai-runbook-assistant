from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.llm_service import LLMService


def main():

    llm = LLMService()

    print("=" * 60)

    if llm.verify_connection():
        print("✓ Connected to Ollama")
    else:
        print("✗ Failed to connect to Ollama")
        return

    print("=" * 60)

    question = "What is Kubernetes?"

    print(f"\nQuestion:\n{question}")

    answer = llm.generate(
        prompt=question
    )

    print("\nAnswer:\n")
    print(answer)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()