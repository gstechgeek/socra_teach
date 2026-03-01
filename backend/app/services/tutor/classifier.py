from __future__ import annotations

import re

# ── Compiled patterns ─────────────────────────────────────────────────────────
# Compiled once at import time — zero cost per classify() call.

_LATEX_PATTERN: re.Pattern[str] = re.compile(
    r"""
    \$[^$]+\$           # inline math $...$
    | \$\$[^$]+\$\$     # display math $$...$$
    | \\frac\{          # \frac{
    | \\int\b           # \int
    | \\sum\b           # \sum
    | \\prod\b          # \prod
    | \\partial\b       # \partial
    | \\nabla\b         # \nabla
    | \\mathbf\{        # \mathbf{
    | \\begin\{equation # \begin{equation
    | \\lim\b           # \lim
    | \\infty\b         # \infty
    | \\sqrt\{          # \sqrt{
    | \\vec\{           # \vec{
    | \\hat\{           # \hat{
    """,
    re.VERBOSE,
)

# ── Keyword sets ──────────────────────────────────────────────────────────────

# Reasoning tier — multi-step proofs, STEM derivations, LaTeX-heavy answers.
_REASONING_KEYWORDS: frozenset[str] = frozenset(
    {
        # Proof language
        "prove",
        "proof",
        "derive",
        "derivation",
        "show that",
        "verify that",
        "demonstrate that",
        "deduce",
        "infer that",
        # Math structures
        "integral",
        "integrand",
        "differentiate",
        "differential equation",
        "eigenvalue",
        "eigenvector",
        "matrix",
        "determinant",
        "transpose",
        "gradient",
        "divergence",
        "curl",
        "laplacian",
        "fourier transform",
        "laplace transform",
        "taylor series",
        "convergence",
        "diverges",
        "series expansion",
        "probability distribution",
        "expected value",
        "variance",
        # Physics / engineering derivations
        "hamiltonian",
        "lagrangian",
        "schrodinger",
        "maxwell",
        "thermodynamics",
        "entropy",
        "momentum",
        "kinetic energy",
        "potential energy",
        "work-energy",
        "newton's law",
        # Complexity signals
        "step by step",
        "step-by-step",
        "work through",
        "solve the following",
        "find the solution",
        "calculate",
        "compute",
        "evaluate the integral",
        "simplify the expression",
        "factor the",
    }
)

# Fast tier — short confirmations and yes/no checks (claude-haiku-4-5).
_FAST_KEYWORDS: frozenset[str] = frozenset(
    {
        "yes or no",
        "true or false",
        "correct or incorrect",
        "is this right",
        "is that right",
        "is this correct",
        "is that correct",
        "am i right",
        "am i correct",
        "does this look right",
        "confirm",
        "just tell me",
        "check this",
        "check my answer",
        "reformat",
        "format this",
        "put this in",
        "is this a",
        "is that a",
        "is this an",
        "is that an",
        "quick question",
        "quick check",
        "just checking",
    }
)

# Local tier — simple recall and definition queries (Llama 3.2-1B).
_LOCAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "what is",
        "what are",
        "define",
        "definition of",
        "what does",
        "what do",
        "who is",
        "who was",
        "who were",
        "when did",
        "when was",
        "where is",
        "where was",
        "list the",
        "list all",
        "name the",
        "name all",
        "give an example",
        "give me an example",
        "give examples",
        "what are the steps",
        "how do you",
        "how does",
        "how do",
        "recall",
        "summarize",
        "summary of",
        "what happened",
        "tell me about",
        "explain what",
        "describe what",
    }
)

# Character thresholds that gate fast/local decisions.
# Messages longer than these thresholds are unlikely to be simple enough
# for the fast or local tier, even if they contain qualifying keywords.
_FAST_MAX_CHARS: int = 80
_LOCAL_MAX_CHARS: int = 150


# ── Private helpers ───────────────────────────────────────────────────────────


def _extract_last_user_message(messages: list[dict[str, str]]) -> str:
    """Return the last user-role message content, lowercased and stripped.

    Scans the message list in reverse so multi-turn history is handled
    correctly — only the most recent user turn drives the routing decision.

    Args:
        messages: OpenAI-format chat history.

    Returns:
        Lowercased, stripped content string, or '' if no user turn exists.
    """
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "").lower().strip()
    return ""


def _has_latex(text: str) -> bool:
    """Return True if text contains LaTeX math notation.

    Args:
        text: Lowercased message content to inspect.

    Returns:
        True if any LaTeX pattern is detected.
    """
    return bool(_LATEX_PATTERN.search(text))


def _matches_any(text: str, keywords: frozenset[str]) -> bool:
    """Return True if text contains any keyword from the set.

    Single-word keywords use ``\\b`` word-boundary matching to prevent
    partial-word false positives. Multi-word phrases use substring matching
    (surrounding context makes false positives unlikely).

    Args:
        text: Lowercased message content.
        keywords: Keyword strings to match against.

    Returns:
        True if at least one keyword is found.
    """
    for kw in keywords:
        if " " in kw:
            if kw in text:
                return True
        else:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return True
    return False


# ── Public API ────────────────────────────────────────────────────────────────


def classify(messages: list[dict[str, str]]) -> str:
    """Classify the query intent and return the appropriate routing tier.

    Applies a prioritised rule cascade with no ML loading:
      1. ``reasoning`` — LaTeX present or STEM/proof keywords detected.
      2. ``fast``      — Short message with confirmation/check keywords.
      3. ``local``     — Short recall/definition query, no math signals.
      4. ``dialogue``  — Default; everything else goes to cloud Socratic model.

    Only the last user message in the history is inspected; earlier turns
    are ignored to avoid stale context contaminating the routing decision.
    Empty lists and system-only histories safely return ``"local"``.

    Args:
        messages: OpenAI-format chat history.

    Returns:
        One of: ``"local"``, ``"dialogue"``, ``"reasoning"``, ``"fast"``.
    """
    text = _extract_last_user_message(messages)
    if not text:
        return "local"

    # Priority 1 — local (short recall/definition queries).
    # Checked before reasoning so that "What is a matrix?" or "Define entropy."
    # are not wrongly elevated to the reasoning tier just because the topic
    # happens to appear in the reasoning keyword set. Local keywords are
    # phrased as question starters ("what is", "define", "list the") which are
    # unambiguous recall patterns; reasoning keywords then catch the deeper ops
    # on the same topics ("derive", "prove", "calculate the determinant of").
    if len(text) <= _LOCAL_MAX_CHARS and _matches_any(text, _LOCAL_KEYWORDS):
        return "local"

    # Priority 2 — reasoning: LaTeX alone is a strong signal even without
    # explicit keyword matches (students who write LaTeX work in formal math).
    if _has_latex(text) or _matches_any(text, _REASONING_KEYWORDS):
        return "reasoning"

    # Priority 3 — fast: short confirmation/check, no LaTeX (caught above).
    if len(text) <= _FAST_MAX_CHARS and _matches_any(text, _FAST_KEYWORDS):
        return "fast"

    # Priority 4 — dialogue: default cloud tier for everything else.
    return "dialogue"
