from abc import ABC, abstractmethod

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from jarvis_multiagent.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, prompt: str) -> str: ...


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete(self, system: str, prompt: str) -> str:
        resp = await self.client.responses.create(
            model=settings.openai_model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_output_tokens=700,
        )
        return resp.output_text


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete(self, system: str, prompt: str) -> str:
        msg = await self.client.messages.create(
            model=settings.anthropic_model,
            max_tokens=700,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if hasattr(block, "text"))


class ProviderFactory:
    @staticmethod
    def create() -> LLMProvider:
        if settings.llm_provider.lower() == "anthropic":
            return AnthropicProvider()
        return OpenAIProvider()
