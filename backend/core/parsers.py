import json
import math

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def finite_float(raw):
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Non-finite JSON")
    return value


def reject_constant(_value):
    raise ValueError("Non-finite JSON")


class StrictJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        try:
            raw = stream.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError("JSON too large")
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            value = json.loads(
                text or "{}",
                object_pairs_hook=unique_object,
                parse_float=finite_float,
                parse_constant=reject_constant,
            )
            if not isinstance(value, dict):
                raise ValueError("Expected object")
            pending = [(value, 0)]
            while pending:
                item, depth = pending.pop()
                if depth > 20:
                    raise ValueError("JSON too deep")
                if isinstance(item, dict):
                    pending.extend((child, depth + 1) for child in item.values())
                    pending.extend((key, depth + 1) for key in item)
                elif isinstance(item, list):
                    pending.extend((child, depth + 1) for child in item)
                elif isinstance(item, str):
                    item.encode("utf-8")
            return value
        except (ValueError, UnicodeError, RecursionError):
            # Do not echo decoder errors or raw field values.
            raise ParseError("Invalid JSON object") from None
