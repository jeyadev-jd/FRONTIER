import httpx
import structlog
from backend.services.llm.base import LLMProvider, LLMResponse
from backend.config import get_settings

logger = structlog.get_logger()


class LMStudioProvider(LLMProvider):
    """LM Studio local LLM provider (OpenAI-compatible endpoint)."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.lmstudio_base_url
        self._model = self._settings.lmstudio_model
        self._temperature = self._settings.llm_temperature
        self._max_tokens = self._settings.llm_max_tokens

    @property
    def provider_name(self) -> str:
        return "lmstudio"

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
            "temperature": temperature or self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        content = choice["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=self._model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self._base_url}/models")
                return r.status_code == 200
        except Exception as e:
            logger.warning("lmstudio.health_check_failed", error=str(e))
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self._base_url}/models")
                r.raise_for_status()
                return [m["id"] for m in r.json().get("data", [])]
        except Exception:
            return []
