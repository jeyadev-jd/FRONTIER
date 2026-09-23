from functools import lru_cache
from backend.services.llm.base import LLMProvider
from backend.config import get_settings


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        from backend.services.llm.ollama import OllamaProvider
        return OllamaProvider()
    elif settings.llm_provider == "lmstudio":
        from backend.services.llm.lmstudio import LMStudioProvider
        return LMStudioProvider()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
