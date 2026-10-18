"""Robust JSON extraction from LLM responses."""

import json
import logging
import re

logger = logging.getLogger(__name__)


def try_parse_agent_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()
    if not cleaned:
        cleaned = text
    for variant in [cleaned, text]:
        md_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", variant, re.DOTALL)
        if md_match:
            try:
                result = json.loads(md_match.group(1))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
        md_no_close = re.search(r"```(?:json)?\s*(\{.*\})", variant, re.DOTALL)
        if md_no_close:
            try:
                result = json.loads(md_no_close.group(1))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
    last_err = None
    for variant in [cleaned, text]:
        try:
            result = json.loads(variant)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError as e:
            last_err = e
        start = variant.find("{")
        if start == -1:
            continue
        for end in range(len(variant), start, -1):
            if variant[end - 1] == "}":
                try:
                    result = json.loads(variant[start:end])
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError as e:
                    last_err = e
                    continue
    if last_err:
        logger.debug("JSON parse final error: %s (pos=%s, last 100 chars: %s)", last_err.msg, last_err.pos, repr(text[-100:]) if text else "")
    return None
