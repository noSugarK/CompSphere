from io import BytesIO

import pytest
from rest_framework.exceptions import ParseError

from core.parsers import StrictJSONParser


@pytest.mark.parametrize(
    "payload",
    [
        b'{"value":1e999}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":"\\ud800"}',
        b'{"\\ud800":"value"}',
        b'{"value":1,"value":2}',
        b'{"nested":{"role":"participant","role":"platform_admin"}}',
        b"[]",
        b'{"nested":' + b"[" * 25 + b"0" + b"]" * 25 + b"}",
        b'{"value":"' + b"x" * 1_048_576 + b'"}',
    ],
)
def test_parser_rejects_ambiguous_unbounded_or_invalid_json(payload):
    with pytest.raises(ParseError) as result:
        StrictJSONParser().parse(BytesIO(payload))
    assert str(result.value.detail) == "Invalid JSON object"


def test_parser_preserves_valid_nested_unicode_and_numeric_values():
    payload = '{"name":"队伍","members":[1,2],"ready":true,"ratio":0.5}'
    assert StrictJSONParser().parse(BytesIO(payload.encode("utf-8"))) == {
        "name": "队伍",
        "members": [1, 2],
        "ready": True,
        "ratio": 0.5,
    }
