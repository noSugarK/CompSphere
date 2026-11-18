"""Treat every model response as untrusted input, never as an executable command."""

import json
import math
from typing import Literal, TypedDict, cast

MAX_OUTPUT_BYTES = 32_768
MAX_JSON_DEPTH = 16
MAX_SAFE_ID = 9_007_199_254_740_991


class ModelOutputError(ValueError):
    """A safe validation failure that never includes the model's raw content."""


class Answer(TypedDict):
    kind: Literal["answer"]
    text: str


class OpenArguments(TypedDict):
    registration_id: int


class DraftFields(TypedDict):
    selected_school_level: Literal["ES", "MS", "HS", "U"]


class DraftArguments(OpenArguments):
    version: int
    fields: DraftFields


class OpenProposal(TypedDict):
    kind: Literal["tool_proposal"]
    tool: Literal["registration.open"]
    arguments: OpenArguments


class DraftProposal(TypedDict):
    kind: Literal["tool_proposal"]
    tool: Literal["registration.update_draft"]
    arguments: DraftArguments


ModelOutput = Answer | OpenProposal | DraftProposal


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ModelOutputError("Duplicate JSON fields are not allowed.")
        result[key] = value
    return result


def _constant(_: str) -> object:
    raise ModelOutputError("JSON numbers must be finite.")


def _float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ModelOutputError("JSON numbers must be finite.")
    return value


def _keys(value: object, expected: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ModelOutputError("JSON fields do not match the allowed schema.")
    return value


def _positive_integer(value: object) -> int:
    # bool is a subclass of int in Python, but is never a valid identifier.
    if type(value) is not int or not 1 <= value <= MAX_SAFE_ID:
        raise ModelOutputError("An identifier or version is invalid.")
    return value


def validate_model_output(raw: str) -> ModelOutput:
    """Parse a bounded JSON response; callers must still authorize each proposal.

    This function deliberately has no database, network, actor or execution access.
    A valid proposal must pass live authorization and state checks in the business
    command gateway before any field can be changed.
    """
    if not isinstance(raw, str):
        raise ModelOutputError("Model output must be JSON text.")
    try:
        if len(raw.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise ModelOutputError("Model output exceeds the size limit.")
        value = json.loads(
            raw,
            object_pairs_hook=_object,
            parse_constant=_constant,
            parse_float=_float,
        )
    except ModelOutputError:
        raise
    except (ValueError, RecursionError, UnicodeError):
        raise ModelOutputError("Model output is not valid bounded JSON.") from None

    pending: list[tuple[object, int]] = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise ModelOutputError("Model output exceeds the nesting limit.")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeError:
                raise ModelOutputError(
                    "Model output contains invalid Unicode."
                ) from None

    if not isinstance(value, dict):
        raise ModelOutputError("Model output must be an object.")
    if value.get("kind") == "answer":
        answer = _keys(value, {"kind", "text"})
        text = answer["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ModelOutputError("Answer text is invalid.")
        return {"kind": "answer", "text": text}

    proposal = _keys(value, {"kind", "tool", "arguments"})
    if proposal["kind"] != "tool_proposal":
        raise ModelOutputError("Model output kind is not allowed.")
    if proposal["tool"] == "registration.open":
        args = _keys(proposal["arguments"], {"registration_id"})
        return {
            "kind": "tool_proposal",
            "tool": "registration.open",
            "arguments": {
                "registration_id": _positive_integer(args["registration_id"])
            },
        }
    if proposal["tool"] == "registration.update_draft":
        args = _keys(proposal["arguments"], {"registration_id", "version", "fields"})
        fields = _keys(args["fields"], {"selected_school_level"})
        level = fields["selected_school_level"]
        if level not in ("ES", "MS", "HS", "U"):
            raise ModelOutputError("School level is invalid.")
        return {
            "kind": "tool_proposal",
            "tool": "registration.update_draft",
            "arguments": {
                "registration_id": _positive_integer(args["registration_id"]),
                "version": _positive_integer(args["version"]),
                "fields": {
                    "selected_school_level": cast(Literal["ES", "MS", "HS", "U"], level)
                },
            },
        }
    raise ModelOutputError("The proposed tool is not allowed.")
