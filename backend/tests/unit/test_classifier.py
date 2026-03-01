from __future__ import annotations

from app.services.tutor.classifier import classify

# ── Helper ────────────────────────────────────────────────────────────────────


def _user(content: str) -> list[dict[str, str]]:
    """Wrap a string in a minimal single-user-turn message list."""
    return [{"role": "user", "content": content}]


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_empty_messages_returns_local() -> None:
    assert classify([]) == "local"


def test_system_only_returns_local() -> None:
    assert classify([{"role": "system", "content": "You are a tutor."}]) == "local"


def test_assistant_only_returns_local() -> None:
    assert classify([{"role": "assistant", "content": "How can I help?"}]) == "local"


def test_last_user_message_is_used_not_first() -> None:
    """When the last user message is simple, result must be local even if
    the first user message was a complex proof request."""
    messages = [
        {"role": "user", "content": "Prove the fundamental theorem of calculus."},
        {"role": "assistant", "content": "What do you know about integrals?"},
        {"role": "user", "content": "What is a derivative?"},
    ]
    assert classify(messages) == "local"


# ── Reasoning tier ────────────────────────────────────────────────────────────


def test_inline_latex_routes_reasoning() -> None:
    assert classify(_user(r"Evaluate $\int_0^1 x^2\,dx$ step by step.")) == "reasoning"


def test_display_latex_routes_reasoning() -> None:
    assert classify(_user(r"Show that $$e^{i\pi} + 1 = 0$$.")) == "reasoning"


def test_frac_command_routes_reasoning() -> None:
    assert classify(_user(r"Simplify \frac{d}{dx}(x^3 + 2x).")) == "reasoning"


def test_prove_keyword_routes_reasoning() -> None:
    assert classify(_user("Prove that the square root of 2 is irrational.")) == "reasoning"


def test_derive_keyword_routes_reasoning() -> None:
    assert classify(_user("Derive the quadratic formula from first principles.")) == "reasoning"


def test_eigenvalue_routes_reasoning() -> None:
    msg = "Explain the eigenvalue decomposition of a symmetric matrix."
    assert classify(_user(msg)) == "reasoning"


def test_step_by_step_phrase_routes_reasoning() -> None:
    msg = "Walk me through Newton's method step by step for f(x)=x^3-2."
    assert classify(_user(msg)) == "reasoning"


def test_hamiltonian_routes_reasoning() -> None:
    msg = "Write the Hamiltonian for a particle in a harmonic potential."
    assert classify(_user(msg)) == "reasoning"


def test_calculate_routes_reasoning() -> None:
    assert classify(_user("Calculate the determinant of this 3x3 matrix.")) == "reasoning"


# ── Fast tier ─────────────────────────────────────────────────────────────────


def test_yes_or_no_routes_fast() -> None:
    assert classify(_user("Is a square a rectangle? Yes or no.")) == "fast"


def test_is_this_correct_routes_fast() -> None:
    assert classify(_user("Is this correct?")) == "fast"


def test_am_i_right_routes_fast() -> None:
    assert classify(_user("Am I right about this?")) == "fast"


def test_check_my_answer_routes_fast() -> None:
    assert classify(_user("Check my answer please.")) == "fast"


def test_fast_keyword_in_long_message_is_not_fast() -> None:
    """Length gate: fast keywords in a long message must not trigger fast tier."""
    long_msg = (
        "I have worked through this integral problem carefully and I believe "
        "my answer of 1/3 is correct — is this correct given the fundamental "
        "theorem of calculus says the integral of x^2 from 0 to 1 equals 1/3?"
    )
    assert classify(_user(long_msg)) != "fast"


# ── Local tier ────────────────────────────────────────────────────────────────


def test_what_is_routes_local() -> None:
    assert classify(_user("What is a matrix?")) == "local"


def test_define_routes_local() -> None:
    assert classify(_user("Define entropy.")) == "local"


def test_who_was_routes_local() -> None:
    assert classify(_user("Who was Euler?")) == "local"


def test_list_the_routes_local() -> None:
    assert classify(_user("List the laws of thermodynamics.")) == "local"


def test_how_does_routes_local() -> None:
    assert classify(_user("How does a hash table work?")) == "local"


def test_local_keyword_in_long_message_is_not_local() -> None:
    """Length gate: local keywords in a long message must not stay local."""
    long_msg = (
        "What is the deep relationship between the eigenvalues and eigenvectors "
        "of a symmetric positive definite matrix, and how does this connect to "
        "the spectral theorem — can you walk me through a concrete example?"
    )
    result = classify(_user(long_msg))
    assert result in ("reasoning", "dialogue")


# ── Dialogue tier ─────────────────────────────────────────────────────────────


def test_open_ended_conceptual_routes_dialogue() -> None:
    msg = "Why do students often confuse the chain rule with the product rule?"
    assert classify(_user(msg)) == "dialogue"


def test_misconception_diagnosis_routes_dialogue() -> None:
    msg = "I thought correlation always implies causation. Can you explain why I'm wrong?"
    assert classify(_user(msg)) == "dialogue"


def test_multi_turn_conceptual_routes_dialogue() -> None:
    messages = [
        {"role": "user", "content": "I'm struggling to understand recursion."},
        {"role": "assistant", "content": "What have you tried so far?"},
        {
            "role": "user",
            "content": (
                "I understand the base case but I can't see how the recursive call "
                "builds toward the correct answer for something like factorial."
            ),
        },
    ]
    assert classify(messages) == "dialogue"


# ── Return-value contract ─────────────────────────────────────────────────────


def test_classify_always_returns_valid_tier() -> None:
    """classify() must always return exactly one of the four valid tier strings."""
    valid = {"local", "dialogue", "reasoning", "fast"}
    inputs: list[list[dict[str, str]]] = [
        [],
        _user(""),
        _user("What is 2 + 2?"),
        _user("Prove Fermat's Last Theorem."),
        _user("Is this right?"),
        [{"role": "system", "content": "x"}, {"role": "user", "content": "hello"}],
    ]
    for msgs in inputs:
        result = classify(msgs)
        assert result in valid, f"Unexpected tier '{result}' for input: {msgs}"
