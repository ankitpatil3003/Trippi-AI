from app.mcp.client import normalize_forecast_days
from app.mcp.tools import coerce_tool_payload


class _Block:
    """Stand-in for an SDK content block object rather than a plain dict."""

    def __init__(self, text: str, type: str = "text") -> None:
        self.text = text
        self.type = type


def test_content_blocks_are_unwrapped_to_the_json_payload():
    """An MCP tool call returns content blocks, not the JSON itself.

    This was returned to the clients untouched, so every live call looked like a
    malformed response and silently fell back to seed data. The services were
    fine; nothing ever read them.
    """
    payload = coerce_tool_payload([{"type": "text", "text": '{"pois": [{"name": "Lisbon Cathedral"}]}'}])

    assert isinstance(payload, dict)
    assert payload["pois"][0]["name"] == "Lisbon Cathedral"


def test_content_blocks_as_objects_are_unwrapped():
    payload = coerce_tool_payload([_Block('{"restaurants": []}')])

    assert payload == {"restaurants": []}


def test_multiple_text_blocks_are_joined_before_parsing():
    payload = coerce_tool_payload([{"type": "text", "text": '{"a":'}, {"type": "text", "text": ' 1}'}])

    assert payload == {"a": 1}


def test_a_genuine_json_array_is_left_alone():
    """Only unwrap when every element is a text block."""
    rows = [{"name": "Prague Castle"}, {"name": "Wenceslas Square"}]

    assert coerce_tool_payload(rows) == rows


def test_dict_and_json_string_payloads_still_pass_through():
    assert coerce_tool_payload({"pois": []}) == {"pois": []}
    assert coerce_tool_payload('{"pois": []}') == {"pois": []}
    assert coerce_tool_payload("not json") == "not json"


def test_normalize_live_mcp_forecast_shape():
    payload = {
        "city": "New York",
        "days": 2,
        "forecast": [
            {
                "date": "2026-07-22",
                "description": "light rain",
                "pop_max": 0.7,
                "temp_min_c": 18,
                "temp_max_c": 24,
            },
            {
                "date": "2026-07-23",
                "description": "clear sky",
                "pop_max": 0.1,
                "temp_min_c": 17,
                "temp_max_c": 26,
            },
        ],
    }
    days = normalize_forecast_days(payload)
    assert len(days) == 2
    assert days[0]["date"] == "2026-07-22"
    assert days[0]["precip_probability"] == 0.7
    assert "rain" in days[0]["summary"]
    assert days[1]["precip_probability"] == 0.1


def test_normalize_rejects_error_payload():
    try:
        normalize_forecast_days({"error": "Rate limit exceeded"})
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "Rate limit" in str(exc)
