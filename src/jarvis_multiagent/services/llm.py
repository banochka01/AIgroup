from abc import ABC, abstractmethod

from jarvis_multiagent.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, prompt: str) -> str: ...


class OpenAIProvider(LLMProvider):
    async def complete(self, system: str, prompt: str) -> str:
        return f"[openai simulated] {prompt[:300]}"


class AnthropicProvider(LLMProvider):
    async def complete(self, system: str, prompt: str) -> str:
        return f"[anthropic simulated] {prompt[:300]}"


class ProviderFactory:
    @staticmethod
    def create() -> LLMProvider:
        if settings.llm_provider.lower() == "anthropic":
            return AnthropicProvider()
        return OpenAIProvider()
