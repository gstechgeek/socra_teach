from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BKTState:
    """Mutable BKT state for a single concept.

    Attributes:
        p_know: P(L_n) — probability the student knows the concept.
        p_slip: P(S) — probability of incorrect response despite knowing.
        p_guess: P(G) — probability of correct response despite not knowing.
        p_transit: P(T) — probability of learning on each opportunity.
    """

    p_know: float
    p_slip: float = 0.1
    p_guess: float = 0.25
    p_transit: float = 0.3

    @classmethod
    def default(cls) -> BKTState:
        """Default BKT priors for a new concept."""
        return cls(p_know=0.0)


def bkt_update(state: BKTState, correct: bool) -> BKTState:
    """Apply one Bayesian update step given an observed response.

    Updates p_know using the standard BKT posterior + transition formula:
    1. Compute likelihoods P(obs | know) and P(obs | ~know).
    2. Posterior P(know | obs) via Bayes' rule.
    3. Learning transition: P(L_{n+1}) = posterior + (1 - posterior) * P(T).

    Args:
        state: Current BKT state for this concept.
        correct: Whether the student's response was correct.

    Returns:
        New BKTState with updated p_know. Other parameters unchanged.
    """
    p_correct_given_know = 1.0 - state.p_slip
    p_correct_given_not_know = state.p_guess

    if correct:
        p_obs = (
            state.p_know * p_correct_given_know + (1.0 - state.p_know) * p_correct_given_not_know
        )
        p_know_posterior = (state.p_know * p_correct_given_know) / p_obs if p_obs > 0 else 0.0
    else:
        p_obs = state.p_know * state.p_slip + (1.0 - state.p_know) * (1.0 - state.p_guess)
        p_know_posterior = (state.p_know * state.p_slip) / p_obs if p_obs > 0 else 0.0

    p_know_new = p_know_posterior + (1.0 - p_know_posterior) * state.p_transit

    return BKTState(
        p_know=p_know_new,
        p_slip=state.p_slip,
        p_guess=state.p_guess,
        p_transit=state.p_transit,
    )


def needs_review(state: BKTState, threshold: float = 0.7) -> bool:
    """Return True if p_know is below the review threshold.

    When True, additional review cards should be generated for this concept.

    Args:
        state: Current BKT state.
        threshold: Mastery threshold (default 0.7 per blueprint).

    Returns:
        True if the concept needs review.
    """
    return state.p_know < threshold


def mastery_level(state: BKTState) -> str:
    """Classify mastery into a human-readable tier.

    Args:
        state: Current BKT state.

    Returns:
        One of: ``not_started``, ``learning``, ``practiced``, ``mastered``.
    """
    if state.p_know < 0.1:
        return "not_started"
    if state.p_know < 0.5:
        return "learning"
    if state.p_know < 0.7:
        return "practiced"
    return "mastered"
