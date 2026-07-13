"""Tests for the ReAct parser and LLM client utilities."""

import json

from sidecar.llm.react import parse_react, REACT_SYSTEM_PROMPT


def test_parse_react_basic():
    text = (
        "Thought: I should fetch the PDB structure.\n"
        'Action: ```json\n{"tool": "pdb_fetch", "input": {"pdb_id": "1CRN"}}\n```'
    )
    steps = parse_react(text)
    assert len(steps) == 1
    assert steps[0].action == "pdb_fetch"
    assert steps[0].input == {"pdb_id": "1CRN"}


def test_parse_react_loose_json():
    text = 'Thought: go\nAction: {"tool": "uniprot_fetch", "input": {"accession": "P12345"}}'
    steps = parse_react(text)
    assert len(steps) == 1
    assert steps[0].action == "uniprot_fetch"


def test_parse_react_no_action():
    text = "Just a normal answer with no Action: block."
    assert parse_react(text) == []


def test_parse_react_empty():
    assert parse_react("") == []
    assert parse_react(None) == []


def test_react_system_prompt_formats():
    descs = "  - tool_a: does a\n  - tool_b: does b"
    prompt = REACT_SYSTEM_PROMPT.format(tool_descriptions=descs)
    assert "tool_a" in prompt
    assert "tool_b" in prompt
    assert "Action:" in prompt


def test_parse_react_multiple_steps():
    text = (
        "Thought: step 1\n"
        'Action: ```json\n{"tool": "pdb_search", "input": {"query": "hemoglobin"}}\n```\n'
        "Thought: step 2\n"
        'Action: ```json\n{"tool": "pdb_fetch", "input": {"pdb_id": "1CRN"}}\n```'
    )
    steps = parse_react(text)
    assert len(steps) == 2
    assert steps[0].action == "pdb_search"
    assert steps[1].action == "pdb_fetch"