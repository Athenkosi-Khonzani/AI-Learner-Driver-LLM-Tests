\
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import abc


@dataclass
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass
class ProviderResponse:
    provider: str
    model: str
    mode: str
    api_success: bool
    latency_s: float
    raw_text: str = ""
    parsed: dict[str, Any] | None = None
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    response_id: str | None = None
    finish_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class ProviderAdapter(abc.ABC):
    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.model = str(model_config["model"])

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str = "structured",
    ) -> ProviderResponse:
        raise NotImplementedError
