"""Strict JSON at subscription protocol/credential boundaries."""

import json
import math


def json_object(text: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Nonfinite JSON number")

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Nonfinite JSON number")
        return parsed

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_float=number)
    except RecursionError:
        raise ValueError("JSON nesting exceeds the protocol limit") from None
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError("JSON nesting exceeds the protocol limit")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values() if isinstance(child, (dict, list)))
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item if isinstance(child, (dict, list)))
    return value
