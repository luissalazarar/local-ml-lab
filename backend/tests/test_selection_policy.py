import pytest

from local_ml_lab.ml.metrics import distribution
from local_ml_lab.ml.selection import confirmation_gate, select_candidate


def candidate(candidate_id, score, units, complexity=1, status="completed"):
    return {
        "candidate_id": candidate_id,
        "model_id": candidate_id,
        "status": status,
        "eligible_for_selection": status == "completed",
        "primary_value": score,
        "complexity_rank": complexity,
        "unit_metrics": [
            {"unit_id": f"u{index}", "primary_value": value}
            for index, value in enumerate(units, 1)
        ],
    }


def test_difference_below_minimum_gain_keeps_reference():
    values = [
        candidate("baseline", 10.0, [10, 10, 10], 0),
        candidate("learned", 9.8, [9.8, 9.8, 9.8]),
    ]
    decision = select_candidate(values, "baseline", "mae", "min")
    assert decision["selected_candidate_id"] == "baseline"


def test_improvement_concentrated_in_one_unit_keeps_reference():
    values = [
        candidate("baseline", 10.0, [10, 10, 10, 10, 10], 0),
        candidate("learned", 8.0, [1, 11, 11, 11, 6]),
    ]
    decision = select_candidate(values, "baseline", "mae", "min")
    assert decision["selected_candidate_id"] == "baseline"
    learned = next(item for item in decision["candidate_decisions"] if item["candidate_id"] == "learned")
    assert learned["passes_gate"] is False


def test_sufficient_consistent_gain_and_simplicity_band():
    values = [
        candidate("baseline", 10.0, [10, 10, 10, 10, 10], 0),
        candidate("complex", 7.0, [7, 7, 7, 7, 7], 5),
        candidate("simple", 7.05, [7.05, 7.05, 7.05, 7.05, 7.05], 2),
    ]
    decision = select_candidate(values, "baseline", "mae", "min")
    assert decision["best_observed_candidate_id"] == "complex"
    assert decision["selected_candidate_id"] == "simple"


def test_incomplete_candidate_never_wins_and_maximize_is_oriented():
    values = [
        candidate("baseline", 0.50, [0.5, 0.5, 0.5], 0),
        candidate("complete", 0.55, [0.55, 0.55, 0.55], 1),
        candidate("partial", 0.99, [0.99], 2, status="timeout"),
    ]
    decision = select_candidate(values, "baseline", "balanced_accuracy", "max")
    assert decision["selected_candidate_id"] == "complete"
    assert decision["best_observed_candidate_id"] == "complete"


def test_zero_error_baseline_cannot_be_claimed_as_relative_improvement():
    values = [
        candidate("baseline", 0.0, [0, 0, 0], 0),
        candidate("learned", 0.0, [0, 0, 0], 1),
    ]
    decision = select_candidate(values, "baseline", "mae", "min")
    assert decision["selected_candidate_id"] == "baseline"
    learned = next(item for item in decision["candidate_decisions"] if item["candidate_id"] == "learned")
    assert learned["reason_code"] == "BASELINE_ERROR_ZERO"


def test_one_unit_standard_deviation_is_null():
    assert distribution([2.0])["sample_std"] is None


def test_unknown_metric_is_not_silently_reoriented():
    with pytest.raises(ValueError, match="UNSUPPORTED_PRIMARY_METRIC"):
        select_candidate(
            [candidate("baseline", 1, [1, 1, 1], 0)],
            "baseline",
            "made_up",
            "min",
        )


def test_confirmation_requires_repeated_gain_for_minimize():
    confirmed = confirmation_gate(
        10.0, 8.0, [10, 10, 10], [8, 8, 11], "mae", "min"
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["won_pairs"] == 2
    rejected = confirmation_gate(
        10.0, 8.0, [10, 10, 10], [11, 8, 11], "mae", "min"
    )
    assert rejected["status"] == "not_confirmed"
    assert rejected["reason_code"] == "GAIN_NOT_REPEATED_IN_CONFIRMATION"


def test_confirmation_orients_maximize_and_requires_three_valid_pairs():
    confirmed = confirmation_gate(
        0.5,
        0.55,
        [0.5, 0.5, 0.5],
        [0.56, 0.55, 0.49],
        "balanced_accuracy",
        "max",
    )
    assert confirmed["status"] == "confirmed"
    incomplete = confirmation_gate(
        0.5,
        0.55,
        [0.5, 0.5, None],
        [0.56, 0.55, 0.60],
        "balanced_accuracy",
        "max",
    )
    assert incomplete["status"] == "not_confirmed"
