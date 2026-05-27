"""
Normalizer: converts a ParsedRow into an EmissionRecord.

Also runs the suspicion rules engine to flag anomalies for analyst review.
"""
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from typing import Optional

from emissions.models import EmissionFactor, EmissionRecord
from ingestion.models import IngestionBatch, RawRecord


def _get_factor(activity_category: str, scope: int, organization=None) -> Optional[EmissionFactor]:
    """Find the best-matching emission factor, preferring org-specific overrides."""
    qs = EmissionFactor.objects.filter(
        activity_category=activity_category,
        scope=scope,
        valid_to__isnull=True,
    ).order_by("-organization")  # org-specific (non-null) first

    if organization:
        org_factor = qs.filter(organization=organization).first()
        if org_factor:
            return org_factor

    return qs.filter(organization__isnull=True).first()


SUSPICION_RULES = []

def suspicion_rule(fn):
    SUSPICION_RULES.append(fn)
    return fn


@suspicion_rule
def rule_zero_quantity(record_data: dict, batch_stats: dict) -> Optional[str]:
    qty = Decimal(record_data.get("normalized_quantity", "0"))
    if qty == Decimal("0"):
        return "zero_quantity"
    return None


@suspicion_rule
def rule_stale_date(record_data: dict, batch_stats: dict) -> Optional[str]:
    activity_date_str = record_data.get("activity_date")
    if not activity_date_str:
        return None
    try:
        activity_date = date.fromisoformat(activity_date_str)
        cutoff = date.today() - timedelta(days=548)  # ~18 months
        if activity_date < cutoff:
            return "stale_date"
    except (ValueError, TypeError):
        pass
    return None


@suspicion_rule
def rule_future_date(record_data: dict, batch_stats: dict) -> Optional[str]:
    activity_date_str = record_data.get("activity_date")
    if not activity_date_str:
        return None
    try:
        activity_date = date.fromisoformat(activity_date_str)
        if activity_date > date.today():
            return "future_date"
    except (ValueError, TypeError):
        pass
    return None


@suspicion_rule
def rule_unknown_unit(record_data: dict, batch_stats: dict) -> Optional[str]:
    unit = record_data.get("raw_unit", "")
    if unit in ("???", "", "unknown") or "???" in unit:
        return "unknown_unit"
    return None


@suspicion_rule
def rule_outlier_quantity(record_data: dict, batch_stats: dict) -> Optional[str]:
    """Flag if normalized CO2e is > 3σ from batch mean for same category."""
    cat = record_data.get("activity_category")
    kg_co2e = record_data.get("_kg_co2e")
    if kg_co2e is None or cat is None:
        return None
    stats = batch_stats.get(cat)
    if not stats or stats.get("count", 0) < 3:
        return None
    mean = stats["mean"]
    std = stats["std"]
    if std > 0 and abs(float(kg_co2e) - mean) > 3 * std:
        return "outlier_3sigma"
    return None


def normalize_row(
    parsed_data: dict,
    batch: IngestionBatch,
    raw_record: RawRecord,
    organization,
    batch_stats: Optional[dict] = None,
) -> Optional[EmissionRecord]:
    """
    Convert parsed row data into an EmissionRecord.
    Returns None if the row is missing required data (e.g. missing date).
    """
    batch_stats = batch_stats or {}

    scope = parsed_data.get("scope")
    activity_category = parsed_data.get("activity_category", "")
    activity_date_str = parsed_data.get("activity_date")

    if not activity_date_str or not scope:
        return None

    try:
        activity_date = date.fromisoformat(activity_date_str)
    except (ValueError, TypeError):
        return None

    try:
        normalized_qty = Decimal(parsed_data.get("normalized_quantity", "0"))
    except InvalidOperation:
        normalized_qty = Decimal("0")

    try:
        raw_qty = Decimal(parsed_data.get("raw_quantity", "0"))
    except InvalidOperation:
        raw_qty = Decimal("0")

    factor = _get_factor(activity_category, scope, organization)

    if factor:
        kg_co2e = normalized_qty * factor.kg_co2e_per_unit
    else:
        kg_co2e = Decimal("0")

    # Run suspicion rules
    check_data = {**parsed_data, "_kg_co2e": float(kg_co2e)}
    reasons = []
    for rule_fn in SUSPICION_RULES:
        result = rule_fn(check_data, batch_stats)
        if result:
            reasons.append(result)

    is_suspicious = len(reasons) > 0
    review_status = (
        EmissionRecord.ReviewStatus.FLAGGED
        if is_suspicious
        else EmissionRecord.ReviewStatus.PENDING
    )

    record = EmissionRecord(
        organization=organization,
        batch=batch,
        raw_record=raw_record,
        source_type=batch.source_type,
        scope=scope,
        activity_category=activity_category,
        activity_date=activity_date,
        vendor=parsed_data.get("vendor", ""),
        location=parsed_data.get("location", ""),
        department=parsed_data.get("department", ""),
        description=parsed_data.get("description", ""),
        raw_quantity=raw_qty,
        raw_unit=parsed_data.get("raw_unit", ""),
        raw_currency=parsed_data.get("raw_currency", ""),
        normalized_quantity=normalized_qty,
        normalized_unit=parsed_data.get("normalized_unit", ""),
        quantity_kg_co2e=kg_co2e,
        emission_factor_used=factor,
        is_suspicious=is_suspicious,
        suspicion_reasons=reasons,
        review_status=review_status,
    )

    return record


def compute_batch_stats(parsed_rows: list) -> dict:
    """
    Compute per-category mean and std of CO2e values for outlier detection.
    Requires two passes — called before normalize_row when a full batch is available.
    """
    import statistics
    from collections import defaultdict

    cat_values: dict[str, list[float]] = defaultdict(list)

    for row_data in parsed_rows:
        cat = row_data.get("activity_category")
        qty = row_data.get("normalized_quantity", "0")
        factor = _get_factor(cat, row_data.get("scope", 3)) if cat else None
        if factor and cat:
            try:
                val = float(Decimal(qty) * factor.kg_co2e_per_unit)
                cat_values[cat].append(val)
            except (InvalidOperation, TypeError):
                pass

    stats = {}
    for cat, vals in cat_values.items():
        if len(vals) >= 2:
            stats[cat] = {
                "mean": statistics.mean(vals),
                "std": statistics.stdev(vals),
                "count": len(vals),
            }
        elif vals:
            stats[cat] = {"mean": vals[0], "std": 0.0, "count": 1}

    return stats
