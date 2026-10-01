"""Regression tests for answer depth and readable conversation history."""

from llm.prompt_templates import build_chat_prompt, build_grounding_repair_prompt


def test_prompt_requests_substantive_broad_answers():
    prompt = build_chat_prompt(
        "[S1] Supporting climate evidence.",
        [],
        "What is global warming?",
    )

    assert "do not stop at a one-sentence definition" in prompt
    assert "how it works, causes, consequences" in prompt
    assert "Source labels look like [S1], [S2]" in prompt
    assert prompt.rstrip().endswith("Assistant:")


def test_prompt_formats_history_as_dialogue_not_python_data():
    prompt = build_chat_prompt(
        "[S1] Supporting climate evidence.",
        [
            {"role": "user", "content": "What causes it?"},
            {"role": "assistant", "content": "Greenhouse gases."},
        ],
        "Can you expand?",
    )

    assert "User: What causes it?" in prompt
    assert "Assistant: Greenhouse gases." in prompt
    assert "{'role':" not in prompt


def test_repair_prompt_prioritizes_direct_support():
    prompt = build_grounding_repair_prompt(
        "[S1] Human activities caused 1.1 degrees of warming.",
        "What is global warming?",
        "Antarctica cooled slightly.",
    )

    assert "topical similarity is not enough" in prompt
    assert "Delete any statement you cannot directly support" in prompt
    assert "Preserve numbers, dates, regions" in prompt
