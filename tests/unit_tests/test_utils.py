"""Tests for shared utility functions."""

from agent.utils import extract_text


def test_extract_text_string():
    assert extract_text("hello") == "hello"


def test_extract_text_list_of_dicts():
    content = [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]
    assert extract_text(content) == "hello world"


def test_extract_text_skips_non_text_blocks():
    content = [
        {"type": "tool_use", "id": "x", "input": {}},
        {"type": "text", "text": "answer"},
    ]
    assert extract_text(content) == "answer"


def test_extract_text_mixed_str_and_dict():
    content = ["plain ", {"type": "text", "text": "mixed"}]
    assert extract_text(content) == "plain mixed"


def test_extract_text_empty_list():
    assert extract_text([]) == ""
