from abc import ABC, abstractmethod
import logging

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from jarvis_multiagent.core.config import settings


logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, prompt: str, *, max_tokens: int | None = None) -> str: ...


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key or "missing", timeout=settings.llm_timeout_seconds)

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def complete(self, system: str, prompt: str, *, max_tokens: int | None = None) -> str:
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not configured")

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens or settings.llm_max_output_tokens,
                temperature=0.2,
            )
        except (APIConnectionError, APITimeoutError, RateLimitError):
            raise
        except Exception as exc:
            logger.exception("OpenAI completion failed")
            raise LLMError(f"OpenAI completion failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMError("OpenAI returned an empty response")
        return content.strip()


class ProviderFactory:
    @staticmethod
    def create() -> LLMProvider:
        if settings.llm_provider.lower() != "openai":
            raise LLMError("Only LLM_PROVIDER=openai is supported in this build")
        return OpenAIProvider()
