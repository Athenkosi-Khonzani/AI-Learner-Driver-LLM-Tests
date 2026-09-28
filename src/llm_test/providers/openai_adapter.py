from __future__ import annotations

import json
import os
import time

from .base import ProviderAdapter, ProviderResponse, ProviderUsage
from .helpers import extract_json_object
from llm_test.benchmark.output_models import StructuredPlan


class OpenAIAdapter(ProviderAdapter):
    @property
    def provider_name(self) -> str:
        return "openai"

    def generate(self, system_prompt: str, user_prompt: str, mode: str = "structured") -> ProviderResponse:
        started = time.perf_counter()
        if not os.getenv("OPENAI_API_KEY"):
            return ProviderResponse(
                provider=self.provider_name, model=self.model, mode=mode,
                api_success=False, latency_s=0.0,
                error_type="RuntimeError",
                error_message="OPENAI_API_KEY is not available in this process.",
            )
        try:
            from openai import OpenAI
            client = OpenAI()
            common = dict(
                model=self.model,
                input=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":user_prompt},
                ],
                max_output_tokens=int(self.model_config.get("max_output_tokens",8192)),
            )
            effort = self.model_config.get("reasoning_effort")
            if effort:
                common["reasoning"] = {"effort":effort}

            if mode == "structured":
                response = client.responses.parse(**common, text_format=StructuredPlan)
                parsed_model = response.output_parsed
                parsed = parsed_model.model_dump() if parsed_model is not None else None
                raw_text = response.output_text or (json.dumps(parsed) if parsed is not None else "")
            else:
                response = client.responses.create(**common)
                raw_text = response.output_text or ""
                try:
                    parsed = extract_json_object(raw_text)
                except Exception:
                    parsed = None
        except Exception as exc:
            return ProviderResponse(
                provider=self.provider_name, model=self.model, mode=mode,
                api_success=False,
                latency_s=time.perf_counter()-started,
                error_type=type(exc).__name__, error_message=str(exc),
            )

        latency = time.perf_counter()-started
        usage_obj = getattr(response,"usage",None)
        input_tokens = getattr(usage_obj,"input_tokens",None)
        output_tokens = getattr(usage_obj,"output_tokens",None)
        total_tokens = getattr(usage_obj,"total_tokens",None)
        input_details = getattr(usage_obj,"input_tokens_details",None)
        cached_tokens = getattr(input_details,"cached_tokens",None)
        output_details = getattr(usage_obj,"output_tokens_details",None)
        reasoning_tokens = getattr(output_details,"reasoning_tokens",None)

        parse_error_type = None
        parse_error_message = None
        if parsed is None:
            parse_error_type = "StructuredParseError"
            parse_error_message = "OpenAI returned no parsed structured output."

        return ProviderResponse(
            provider=self.provider_name, model=self.model, mode=mode,
            api_success=True, latency_s=latency,
            raw_text=raw_text, parsed=parsed,
            usage=ProviderUsage(
                input_tokens=input_tokens, output_tokens=output_tokens,
                total_tokens=total_tokens, cached_input_tokens=cached_tokens,
                reasoning_tokens=reasoning_tokens,
            ),
            response_id=getattr(response,"id",None),
            finish_reason=getattr(response,"status",None),
            error_type=parse_error_type, error_message=parse_error_message,
        )
