from __future__ import annotations

from app.services.tutor.socratic import build_socratic_prompt


def test_local_prompt_prepends_system_message() -> None:
    messages = [{"role": "user", "content": "What is a matrix?"}]
    result = build_socratic_prompt(messages, cloud=False)

    assert result[0]["role"] == "system"
    assert len(result) == 2
    assert result[1] == messages[0]


def test_cloud_prompt_uses_richer_content() -> None:
    messages = [{"role": "user", "content": "Prove the Pythagorean theorem."}]
    local = build_socratic_prompt(messages, cloud=False)
    cloud = build_socratic_prompt(messages, cloud=True)

    assert "Bloom" in cloud[0]["content"]
    assert "Bloom" not in local[0]["content"]


def test_existing_system_message_is_replaced() -> None:
    messages = [
        {"role": "system", "content": "old system prompt"},
        {"role": "user", "content": "Hello"},
    ]
    result = build_socratic_prompt(messages)

    assert result[0]["role"] == "system"
    assert result[0]["content"] != "old system prompt"
    assert len(result) == 2  # system + one user message


def test_empty_messages_returns_system_only() -> None:
    result = build_socratic_prompt([])
    assert len(result) == 1
    assert result[0]["role"] == "system"
