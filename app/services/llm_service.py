import requests

from app.utils.logger import get_logger
from app.utils.config import settings


logger = get_logger(__name__)

OLLAMA_GENERATE_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"

LLM_MODEL = "qwen3:8b"

REQUEST_TIMEOUT = 120


class LLMService:

    def __init__(self):
        self.generate_url = OLLAMA_GENERATE_URL
        self.tags_url = f"{settings.OLLAMA_BASE_URL}/api/tags"

    def verify_connection(self) -> bool:
        """
        Verify Ollama server is reachable.
        """

        try:
            response = requests.get(
                self.tags_url,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            logger.info(
                "Successfully connected to Ollama"
            )

            return True

        except Exception as ex:
            logger.exception(
                f"Failed to connect to Ollama: {ex}"
            )

            return False

    def generate(
        self,
        prompt: str
    ) -> str:
        """
        Generate response using Ollama.
        """

        payload = {
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False
        }

        try:
            logger.info(
                f"Generating response using model: {LLM_MODEL}"
            )

            response = requests.post(
                self.generate_url,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            answer = data.get(
                "response",
                ""
            )

            logger.info(
                "Response generated successfully"
            )

            return answer

        except Exception as ex:
            logger.exception(
                "LLM generation failed: %s",
                str(ex)
            )

            return ""