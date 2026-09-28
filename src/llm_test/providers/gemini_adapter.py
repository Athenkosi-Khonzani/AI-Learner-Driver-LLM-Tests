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

    def generate(self, system_prompt: str, user_prompt: str, mode: str = "structured") -> ProviderResponse:
        started = time.perf_counter()
        if not os.getenv("GEMINI_API_KEY"):
            return ProviderResponse(
                provider=self.provider_name, model=self.model, mode=mode,
                api_success=False, latency_s=0.0,
                error_type="RuntimeError",
                error_message="GEMINI_API_KEY is not available in this process.",
            )
        try:
            from google import genai
            from google.genai import types
            client = genai.Client()
            config_kwargs = {
                "system_instruction": system_prompt,
                "thinking_config": types.ThinkingConfig(
                    thinking_level=self.model_config.get("thinking_level","medium")
                ),
                "max_output_tokens": int(self.model_config.get("max_output_tokens",8192)),
            }
            if mode == "structured":
                config_kwargs.update(
                    response_mime_type="application/json",
                    response_json_schema=StructuredPlan.model_json_schema(),
                )
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            return ProviderResponse(
                provider=self.provider_name, model=self.model, mode=mode,
                api_success=False, latency_s=time.perf_counter()-started,
                error_type=type(exc).__name__, error_message=str(exc),
            )

        latency = time.perf_counter()-started
        raw_text = response.text or ""
        parsed = None
        parse_error_type = None
        parse_error_message = None
        try:
            parsed_attr = getattr(response,"parsed",None)
            if isinstance(parsed_attr,dict):
                parsed = parsed_attr
            elif hasattr(parsed_attr,"model_dump"):
                parsed = parsed_attr.model_dump()
            else:
                parsed = json.loads(raw_text) if mode == "structured" else extract_json_object(raw_text)
        except Exception as exc:
            parse_error_type = type(exc).__name__
            parse_error_message = str(exc)

        usage_obj = getattr(response,"usage_metadata",None)
        input_tokens = getattr(usage_obj,"prompt_token_count",None)
        output_tokens = getattr(usage_obj,"candidates_token_count",None)
        total_tokens = getattr(usage_obj,"total_token_count",None)
        reasoning_tokens = getattr(usage_obj,"thoughts_token_count",None)
        cached_tokens = getattr(usage_obj,"cached_content_token_count",None)
        finish_reason = None
        candidates = getattr(response,"candidates",None) or []
        if candidates:
            reason = getattr(candidates[0],"finish_reason",None)
            if reason is not None:
                finish_reason = getattr(reason,"name",None) or str(reason)

        return ProviderResponse(
            provider=self.provider_name, model=self.model, mode=mode,
            api_success=True, latency_s=latency,
            raw_text=raw_text, parsed=parsed,
            usage=ProviderUsage(
                input_tokens=input_tokens, output_tokens=output_tokens,
                total_tokens=total_tokens, cached_input_tokens=cached_tokens,
                reasoning_tokens=reasoning_tokens,
            ),
            response_id=getattr(response,"response_id",None),
            finish_reason=finish_reason,
            error_type=parse_error_type, error_message=parse_error_message,
        )
