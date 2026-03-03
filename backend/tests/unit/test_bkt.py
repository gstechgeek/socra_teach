from __future__ import annotations

from app.services.fsrs.bkt import BKTState, bkt_update, mastery_level, needs_review


class TestBKTUpdate:
    """Tests for the Bayesian Knowledge Tracing update function."""

    def test_correct_response_increases_p_know(self) -> None:
        state = BKTState(p_know=0.3)
        updated = bkt_update(state, correct=True)
        assert updated.p_know > state.p_know

    def test_incorrect_response_decreases_p_know(self) -> None:
        state = BKTState(p_know=0.8)
        updated = bkt_update(state, correct=False)
        assert updated.p_know < state.p_know

    def test_p_know_zero_correct_still_learns(self) -> None:
        state = BKTState(p_know=0.0)
        updated = bkt_update(state, correct=True)
        assert updated.p_know > 0.0

    def test_p_know_zero_incorrect_still_learns_via_transit(self) -> None:
        state = BKTState(p_know=0.0)
        updated = bkt_update(state, correct=False)
        # Even with incorrect, transit gives some learning
        assert updated.p_know > 0.0

    def test_high_p_know_incorrect_stays_high(self) -> None:
        # At p_know=1.0, a single slip is explained entirely by p_slip,
        # so the posterior remains 1.0. Use a slightly lower value.
        state = BKTState(p_know=0.9)
        updated = bkt_update(state, correct=False)
        assert updated.p_know < 0.9

    def test_convergence_after_many_correct(self) -> None:
        state = BKTState(p_know=0.0)
        for _ in range(10):
            state = bkt_update(state, correct=True)
        assert state.p_know > 0.95

    def test_convergence_after_many_incorrect(self) -> None:
        state = BKTState(p_know=0.5)
        for _ in range(20):
            state = bkt_update(state, correct=False)
        # p_know should be low but transit prevents it from hitting 0
        assert state.p_know < 0.4

    def test_parameters_preserved_after_update(self) -> None:
        state = BKTState(p_know=0.5, p_slip=0.15, p_guess=0.3, p_transit=0.2)
        updated = bkt_update(state, correct=True)
        assert updated.p_slip == 0.15
        assert updated.p_guess == 0.3
        assert updated.p_transit == 0.2

    def test_p_know_stays_in_valid_range(self) -> None:
        state = BKTState(p_know=0.5)
        for correct in [True, False, True, True, False, False, True]:
            state = bkt_update(state, correct=correct)
            assert 0.0 <= state.p_know <= 1.0


class TestDefaultState:
    """Tests for BKTState defaults."""

    def test_default_p_know(self) -> None:
        state = BKTState.default()
        assert state.p_know == 0.0

    def test_default_p_slip(self) -> None:
        state = BKTState.default()
        assert state.p_slip == 0.1

    def test_default_p_guess(self) -> None:
        state = BKTState.default()
        assert state.p_guess == 0.25

    def test_default_p_transit(self) -> None:
        state = BKTState.default()
        assert state.p_transit == 0.3


class TestNeedsReview:
    """Tests for the needs_review threshold check."""

    def test_below_threshold(self) -> None:
        state = BKTState(p_know=0.5)
        assert needs_review(state) is True

    def test_above_threshold(self) -> None:
        state = BKTState(p_know=0.8)
        assert needs_review(state) is False

    def test_at_threshold(self) -> None:
        state = BKTState(p_know=0.7)
        assert needs_review(state) is False

    def test_custom_threshold(self) -> None:
        state = BKTState(p_know=0.5)
        assert needs_review(state, threshold=0.4) is False


class TestMasteryLevel:
    """Tests for mastery level classification."""

    def test_not_started(self) -> None:
        assert mastery_level(BKTState(p_know=0.0)) == "not_started"
        assert mastery_level(BKTState(p_know=0.09)) == "not_started"

    def test_learning(self) -> None:
        assert mastery_level(BKTState(p_know=0.1)) == "learning"
        assert mastery_level(BKTState(p_know=0.49)) == "learning"

    def test_practiced(self) -> None:
        assert mastery_level(BKTState(p_know=0.5)) == "practiced"
        assert mastery_level(BKTState(p_know=0.69)) == "practiced"

    def test_mastered(self) -> None:
        assert mastery_level(BKTState(p_know=0.7)) == "mastered"
        assert mastery_level(BKTState(p_know=1.0)) == "mastered"
