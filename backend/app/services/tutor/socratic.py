from __future__ import annotations

# Compact structured prompt for the local 1B model.
# Keeps token count low — the 1B model responds better to explicit rules
# than to open-ended prose instructions.
_SYSTEM_PROMPT_LOCAL = """\
You are a Socratic tutor. NEVER give direct answers.
RULES:
1. Ask ONE question per response.
2. If student is correct: praise briefly, ask a deeper question.
3. If student is wrong: give a hint, then rephrase the question.
4. If student says "I don't know": break into a smaller sub-question.
5. After 3 failed attempts on the same step: explain that step, then ask about the NEXT step.
6. Always end your response with a question.
"""

# Richer prompt for cloud models (claude-sonnet-4-5, deepseek-r1).
# References Bloom's Taxonomy and the full Socratic cycle.
_SYSTEM_PROMPT_CLOUD = """\
You are an expert Socratic tutor operating on the Elicit → Probe → Diagnose → Deepen → Consolidate cycle.
Guide the student using Bloom's Taxonomy: start at Remember/Understand, escalate toward Analyze/Evaluate/Create.

RULES:
1. Ask ONE focused question per response.
2. Correct answer → praise briefly + ask a deeper Bloom's-level question.
3. Wrong answer → identify the misconception, give a minimal hint, rephrase.
4. "I don't know" → decompose into a smaller sub-question.
5. 3+ failed attempts on the same concept → provide a direct explanation, then ask a comprehension check.
6. Always end with a question.
7. Use LaTeX for all mathematical notation (inline: $...$, display: $$...$$).
"""


def build_socratic_prompt(
    messages: list[dict[str, str]],
    cloud: bool = False,
    context: str | None = None,
) -> list[dict[str, str]]:
    """Prepend the appropriate Socratic system prompt to the message history.

    When context is provided (retrieved textbook passages), it is appended
    to the system message so the model grounds its Socratic questions in
    the student's actual course material.

    Args:
        messages: Raw user/assistant chat history in OpenAI format.
        cloud: If True, use the richer cloud prompt; else use the compact
               local prompt suited for the 1B model.
        context: Optional pre-formatted string of retrieved textbook passages
                 to inject into the system message. None means no RAG context
                 (e.g. no documents uploaded yet).

    Returns:
        Message list with the Socratic system prompt as the first entry.
        Any pre-existing system message is replaced.
    """
    prompt = _SYSTEM_PROMPT_CLOUD if cloud else _SYSTEM_PROMPT_LOCAL

    if context:
        prompt = (
            prompt + "\n8. When referencing textbook content, cite the source as "
            "[p. N] where N is the page number from the CONTEXT header."
            "\n\nCONTEXT (passages from the student's textbook — "
            "ground your Socratic questions in these):\n" + context
        )

    system = {"role": "system", "content": prompt}

    if messages and messages[0].get("role") == "system":
        return [system, *messages[1:]]
    return [system, *messages]
