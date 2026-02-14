import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add mcp-server to path so we can import server
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp-server"))
)

import server


@pytest.fixture
def mock_cozo():
    with patch("server.requests.post") as mock_post:
        yield mock_post


def test_add_person_success(mock_cozo):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True, "rows": []}
    mock_response.raise_for_status.return_value = None
    mock_cozo.return_value = mock_response

    result = server.add_person("John Doe", '{"age": 30}')

    assert "Added person: John Doe" in result
    assert mock_cozo.called

    # Verify call arguments
    args, kwargs = mock_cozo.call_args
    payload = kwargs["json"]
    assert "John Doe" in payload["params"]["name"]
    assert payload["params"]["data"] == {"age": 30}


def test_add_person_invalid_json(mock_cozo):
    result = server.add_person("John Doe", "{invalid json}")
    assert "Error: properties must be a valid JSON string" in result
    assert not mock_cozo.called


def test_list_relation_types(mock_cozo):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "ok": True,
        "rows": [["parent_child"], ["spouse"]],
    }
    mock_response.raise_for_status.return_value = None
    mock_cozo.return_value = mock_response

    result = server.list_relation_types()
    assert "Existing Relation Types: parent_child, spouse" in result


def test_inspect_person_schema(mock_cozo):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "ok": True,
        "rows": [["Alice", {"job": "Dev"}], ["Bob", {"job": "Designer"}]],
    }
    mock_response.raise_for_status.return_value = None
    mock_cozo.return_value = mock_response

    result = server.inspect_person_schema()
    assert "Alice" in result
    assert "Bob" in result
    assert '{"job": "Dev"}' in result
