from __future__ import annotations

import math

POLICY_VERSION = "selection-policy-2.0"


def thresholds(
    metric_id: str, baseline_value: float, target_scale: float = 1.0
) -> tuple[float, float, float]:
    epsilon = max(1e-12, abs(target_scale) * 1e-12)
    if metric_id in {"mae", "rmse"}:
        reference_error = max(0.0, float(baseline_value))
        return reference_error * 0.01, reference_error * 0.03, epsilon
    if metric_id in {"accuracy", "balanced_accuracy", "macro_f1"}:
        return 0.005, 0.02, epsilon
    if metric_id == "r2":
        return 0.01, 0.02, epsilon
    raise ValueError("UNSUPPORTED_PRIMARY_METRIC")


def oriented_improvement(candidate: float, baseline: float, direction: str) -> float:
    return candidate - baseline if direction == "max" else baseline - candidate


def _score_key(candidate: dict, direction: str) -> tuple:
    value = candidate["primary_value"]
    return (
        -value if direction == "max" else value,
        candidate["complexity_rank"],
        candidate["candidate_id"],
    )


def select_candidate(
    candidates: list[dict],
    baseline_id: str,
    metric_id: str,
    direction: str,
    target_scale: float = 1.0,
    methodology_blocked: bool = False,
) -> dict:
    complete = [
        candidate
        for candidate in candidates
        if candidate.get("status") == "completed"
        and candidate.get("eligible_for_selection")
        and candidate.get("primary_value") is not None
        and math.isfinite(float(candidate["primary_value"]))
    ]
    if not complete:
        raise ValueError("NO_COMPLETE_CANDIDATES")
    baseline = next(
        (candidate for candidate in complete if candidate["candidate_id"] == baseline_id), None
    )
    if baseline is None:
        raise ValueError("BASELINE_NOT_COMPLETED")
    best_observed = sorted(complete, key=lambda value: _score_key(value, direction))[0]
    tolerance, minimum_gain, epsilon = thresholds(
        metric_id, baseline["primary_value"], target_scale
    )
    decisions = []
    passing = []
    baseline_units = {
        unit["unit_id"]: unit
        for unit in baseline.get("unit_metrics", [])
        if unit.get("primary_value") is not None
    }
    for candidate in complete:
        paired = []
        missing_reasons = []
        for unit in candidate.get("unit_metrics", []):
            baseline_unit = baseline_units.get(unit["unit_id"])
            if unit.get("primary_value") is None or not baseline_unit:
                missing_reasons.append(
                    {
                        "unit_id": unit["unit_id"],
                        "reason": unit.get("reason_code") or "BASELINE_UNIT_UNDEFINED",
                    }
                )
                continue
            paired.append(
                oriented_improvement(
                    float(unit["primary_value"]),
                    float(baseline_unit["primary_value"]),
                    direction,
                )
            )
        joint_gain = oriented_improvement(
            float(candidate["primary_value"]), float(baseline["primary_value"]), direction
        )
        paired_sorted = sorted(paired)
        median_gain = (
            paired_sorted[len(paired_sorted) // 2]
            if len(paired_sorted) % 2
            else (
                (
                    paired_sorted[len(paired_sorted) // 2 - 1]
                    + paired_sorted[len(paired_sorted) // 2]
                )
                / 2
                if paired_sorted
                else None
            )
        )
        wins = sum(value > epsilon for value in paired)
        required_wins = math.ceil(0.60 * len(paired)) if paired else 0
        zero_error_block = metric_id in {"mae", "rmse"} and baseline["primary_value"] <= epsilon
        gate = (
            candidate["candidate_id"] != baseline_id
            and not methodology_blocked
            and not zero_error_block
            and joint_gain + epsilon >= minimum_gain
            and len(paired) >= 3
            and wins >= required_wins
            and median_gain is not None
            and median_gain > epsilon
        )
        detail = {
            "candidate_id": candidate["candidate_id"],
            "joint_improvement": joint_gain,
            "paired_units": len(paired),
            "won_units": wins,
            "required_wins": required_wins,
            "median_paired_improvement": median_gain,
            "undefined_units": missing_reasons,
            "passes_gate": gate,
            "reason_code": (
                "BASELINE"
                if candidate["candidate_id"] == baseline_id
                else "METHODOLOGY_BLOCKED"
                if methodology_blocked
                else "BASELINE_ERROR_ZERO"
                if zero_error_block
                else "PRACTICAL_AND_CONSISTENT_IMPROVEMENT"
                if gate
                else "IMPROVEMENT_GATE_NOT_MET"
            ),
        }
        decisions.append(detail)
        if gate:
            passing.append(candidate)
    if not passing:
        selected = baseline
        reason = "REFERENCE_PREFERRED_NO_PRACTICAL_CONSISTENT_IMPROVEMENT"
    else:
        best_passing = sorted(passing, key=lambda value: _score_key(value, direction))[0]
        if direction == "min":
            band = [
                candidate
                for candidate in passing
                if candidate["primary_value"] <= best_passing["primary_value"] + tolerance + epsilon
            ]
        else:
            band = [
                candidate
                for candidate in passing
                if candidate["primary_value"] >= best_passing["primary_value"] - tolerance - epsilon
            ]
        selected = sorted(
            band,
            key=lambda value: (
                value["complexity_rank"],
                -value["primary_value"] if direction == "max" else value["primary_value"],
                value["candidate_id"],
            ),
        )[0]
        reason = "PRACTICAL_CONSISTENT_IMPROVEMENT_WITH_SIMPLICITY_BAND"
    selected_detail = next(
        item for item in decisions if item["candidate_id"] == selected["candidate_id"]
    )
    return {
        "policy_version": POLICY_VERSION,
        "primary_metric_id": metric_id,
        "direction": direction,
        "baseline_candidate_id": baseline_id,
        "best_observed_candidate_id": best_observed["candidate_id"],
        "selected_candidate_id": selected["candidate_id"],
        "model_id": selected["model_id"],
        "tolerance": tolerance,
        "minimum_practical_gain": minimum_gain,
        "numeric_epsilon": epsilon,
        "joint_improvement": selected_detail["joint_improvement"],
        "paired_units": selected_detail["paired_units"],
        "won_units": selected_detail["won_units"],
        "reason_code": reason,
        "reason": (
            "Los modelos probados no superaron el umbral de mejora y consistencia; conservamos la referencia más sencilla."
            if selected["candidate_id"] == baseline_id
            else "La mejora superó el umbral práctico y fue consistente; dentro de resultados equivalentes preferimos menor complejidad."
        ),
        "candidate_decisions": decisions,
        "thresholds_are_product_policy": True,
        "statistical_significance_claimed": False,
    }
