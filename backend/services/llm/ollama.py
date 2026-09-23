import httpx
import json
import structlog
from backend.services.llm.base import LLMProvider, LLMResponse
from backend.config import get_settings

logger = structlog.get_logger()


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.ollama_base_url
        self._model = self._settings.ollama_model
        self._temperature = self._settings.llm_temperature
        self._max_tokens = self._settings.llm_max_tokens

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self._temperature,
                "num_predict": max_tokens or self._max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "")
        return LLMResponse(
            content=content,
            model=self._model,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self._base_url}/api/tags")
                if r.status_code != 200:
                    return False
                models = [m["name"] for m in r.json().get("models", [])]
                available = any(
                    self._model in m or m.startswith(self._model.split(":")[0])
                    for m in models
                )
                if not available:
                    logger.warning(
                        "ollama.model_not_found",
                        model=self._model,
                        available=models,
                    )
                return True
        except Exception as e:
            logger.warning("ollama.health_check_failed", error=str(e))
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self._base_url}/api/tags")
                r.raise_for_status()
                return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []
