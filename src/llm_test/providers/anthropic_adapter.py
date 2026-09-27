\
from __future__ import annotations

import json
import os
import time

from .base import ProviderAdapter, ProviderResponse, ProviderUsage
from .helpers import extract_json_object
from llm_test.benchmark.output_models import StructuredPlan


class AnthropicAdapter(ProviderAdapter):
    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _text_from_message(self, message) -> str:
        pieces: list[str] = []
        for block in getattr(message, "content", []) or []:
            if getattr(block, "type", None) == "text":
                pieces.append(getattr(block, "text", ""))
        return "".join(pieces)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str = "structured",
    ) -> ProviderResponse:

        started = time.perf_counter()

        try:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not available in this process."
                )

            import anthropic

            client = anthropic.Anthropic()

            kwargs = dict(
                model=self.model,
                max_tokens=int(
                    self.model_config.get("max_output_tokens", 512)
                ),
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )

            thinking_mode = self.model_config.get("thinking")
            if thinking_mode == "adaptive":
                kwargs["thinking"] = {"type": "adaptive"}
            elif thinking_mode == "disabled":
                kwargs["thinking"] = {"type": "disabled"}

            if mode == "structured":
                # Anthropic JSON outputs use output_config.format.
                # Pydantic's JSON schema is supplied directly so that the
                # returned text is still preserved for benchmark logging.
                output_config = {
                    "format": {
                        "type": "json_schema",
                        "schema": StructuredPlan.model_json_schema(),
                    }
                }

                effort = self.model_config.get("effort")
                if effort:
                    output_config["effort"] = effort

                kwargs["output_config"] = output_config

            message = client.messages.create(**kwargs)

            raw_text = self._text_from_message(message)
            parsed = (
                json.loads(raw_text)
                if mode == "structured"
                else extract_json_object(raw_text)
            )

            latency = time.perf_counter() - started

            usage_obj = getattr(message, "usage", None)
            input_tokens = getattr(usage_obj, "input_tokens", None)
            output_tokens = getattr(usage_obj, "output_tokens", None)

            cache_read = getattr(
                usage_obj,
                "cache_read_input_tokens",
                None
            )

            return ProviderResponse(
                provider=self.provider_name,
                model=self.model,
                mode=mode,
                api_success=True,
                latency_s=latency,
                raw_text=raw_text,
                parsed=parsed,
                usage=ProviderUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=(
                        input_tokens + output_tokens
                        if isinstance(input_tokens, int)
                        and isinstance(output_tokens, int)
                        else None
                    ),
                    cached_input_tokens=cache_read,
                ),
                response_id=getattr(message, "id", None),
                finish_reason=getattr(message, "stop_reason", None),
            )

        except Exception as exc:
            return ProviderResponse(
                provider=self.provider_name,
                model=self.model,
                mode=mode,
                api_success=False,
                latency_s=time.perf_counter() - started,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
