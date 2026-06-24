import requests
from requests.exceptions import ReadTimeout, RequestException

from app.utils.logger import get_logger
from app.utils.config import settings


logger = get_logger(__name__)

OLLAMA_GENERATE_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"

LLM_MODEL = "qwen3:8b"

REQUEST_TIMEOUT = 300
MAX_RETRIES = 2


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
                timeout=(10, 30)
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

            attempts = 0
            while attempts <= MAX_RETRIES:
                try:
                    response = requests.post(
                        self.generate_url,
                        json=payload,
                        timeout=(20, REQUEST_TIMEOUT),
                    )
                    response.raise_for_status()
                    data = response.json()
                    answer = data.get("response", "")
                    logger.info("Response generated successfully")
                    return answer
                except ReadTimeout as timeout_exc:
                    attempts += 1
                    logger.warning(
                        "Ollama request timed out (attempt %s/%s): %s",
                        attempts,
                        MAX_RETRIES,
                        timeout_exc,
                    )
                    if attempts > MAX_RETRIES:
                        raise
                except RequestException as req_exc:
                    logger.exception("LLM request failed: %s", req_exc)
                    raise

        except Exception as ex:
            logger.exception("LLM generation failed: %s", str(ex))
            return ""