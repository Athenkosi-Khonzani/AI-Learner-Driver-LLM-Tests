from __future__ import annotations

import json
import os
import time

from .base import ProviderAdapter, ProviderResponse, ProviderUsage
from .helpers import extract_json_object
from llm_test.benchmark.output_models import StructuredPlan


class GeminiAdapter(ProviderAdapter):
    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str = "structured",
    ) -> ProviderResponse:

        started = time.perf_counter()

        try:
            if not os.getenv("GEMINI_API_KEY"):
                raise RuntimeError(
                    "GEMINI_API_KEY is not available in this process."
                )

            from google import genai
            from google.genai import types

            client = genai.Client()

            thinking_level = self.model_config.get(
                "thinking_level",
                "minimal"
            )

            config_kwargs = {
                "system_instruction": system_prompt,
                "thinking_config": types.ThinkingConfig(
                    thinking_level=thinking_level
                ),
            }

            if mode == "structured":
                # IMPORTANT:
                # Use response_json_schema rather than response_schema.
                #
                # StructuredPlan uses ConfigDict(extra="forbid"), so its
                # Pydantic JSON schema contains "additionalProperties": false.
                # Gemini's older/OpenAPI response_schema path rejects that
                # field for this request. response_json_schema is the SDK/API
                # path intended for standard JSON Schema and supports it.
                config_kwargs.update(
                    response_mime_type="application/json",
                    response_json_schema=StructuredPlan.model_json_schema(),
                )

            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            raw_text = response.text or ""

            if mode == "structured":
                # response.parsed may be populated when a JSON schema is used.
                # Keep a robust text fallback so benchmark logging works across
                # SDK versions.
                parsed_attr = getattr(response, "parsed", None)

                if isinstance(parsed_attr, dict):
                    parsed = parsed_attr
                elif hasattr(parsed_attr, "model_dump"):
                    parsed = parsed_attr.model_dump()
                else:
                    parsed = json.loads(raw_text)
            else:
                parsed = extract_json_object(raw_text)

            latency = time.perf_counter() - started

            usage_obj = getattr(response, "usage_metadata", None)
            input_tokens = getattr(
                usage_obj,
                "prompt_token_count",
                None
            )
            output_tokens = getattr(
                usage_obj,
                "candidates_token_count",
                None
            )
            total_tokens = getattr(
                usage_obj,
                "total_token_count",
                None
            )
            reasoning_tokens = getattr(
                usage_obj,
                "thoughts_token_count",
                None
            )
            cached_tokens = getattr(
                usage_obj,
                "cached_content_token_count",
                None
            )

            finish_reason = None
            candidates = getattr(response, "candidates", None) or []

            if candidates:
                reason = getattr(candidates[0], "finish_reason", None)

                if reason is not None:
                    finish_reason = (
                        getattr(reason, "name", None)
                        or str(reason)
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
                    total_tokens=total_tokens,
                    cached_input_tokens=cached_tokens,
                    reasoning_tokens=reasoning_tokens,
                ),
                response_id=getattr(response, "response_id", None),
                finish_reason=finish_reason,
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
