\
from __future__ import annotations

import json
import re


def extract_json_object(text: str) -> dict:
    """
    Prompt-only mode helper. Native structured mode should not need this.
    """
    text = text.strip()

    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        text = fenced.group(1).strip()

    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Top-level JSON must be an object.")
        return value
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in model response.")

    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("Top-level JSON must be an object.")
    return value
