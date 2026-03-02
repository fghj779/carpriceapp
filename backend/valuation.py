"""Valuation engine for used-car pricing and depreciation.

Current Value = (Base Price × Depreciation(age)) × f(mileage) × f(condition) ×
f(region_segment)
"""

from dataclasses import dataclass
from typing import Dict, List


COUNTRY_SEGMENT_DEMAND = {
    "UAE": {
        "SUV": 1.12,
        "TRUCK": 1.04,
        "COMPACT": 0.94,
        "DEFAULT": 1.03,
    },
    "KR": {
        "COMPACT": 1.10,
        "HYBRID": 1.08,
        "SUV": 0.94,
        "DEFAULT": 1.00,
    },
    "USA": {
        "TRUCK": 1.07,
        "SUV": 1.03,
        "COMPACT": 0.98,
        "DEFAULT": 1.00,
    },
    "DEFAULT": {"DEFAULT": 1.00},
}


BASE_YEAR1_RATE = 0.15
BASE_YEAR2_PLUS_RATE = 0.10
BASELINE_ANNUAL_KM = 15000


def clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def depreciation_rate_factor(age_years: float) -> float:
    """Piece-wise depreciation factor.

    Weighting:
    - first year has strong impact (15%)
    - remaining years follow 10%
    """
    if age_years <= 0:
        return 1.0

    first_year = min(age_years, 1.0)
    rest_years = max(age_years - 1.0, 0.0)

    return (1.0 - BASE_YEAR1_RATE) ** first_year * (1.0 - BASE_YEAR2_PLUS_RATE) ** rest_years


def mileage_factor(age_years: float, mileage_km: float) -> float:
    """
    Usage adjustment.

    - Expected usage is 15,000 km/year.
    - Each km above expected adds a small penalty.
    - Bounded to avoid unrealistic extremes.
    """
    expected_km = max(age_years, 0.25) * BASELINE_ANNUAL_KM
    excess = max(0.0, mileage_km - expected_km)
    raw = 1.0 - (excess / 1000000.0)
    return clamp(raw, 0.60, 1.20)


def condition_factor(accident_history_severity: float) -> float:
    """
    Condition factor from accident severity where severity is 0..5.

    Severity 0: no loss (1.0)
    Severity 5: max discount to 0.70
    """
    sev = clamp(float(accident_history_severity), 0.0, 5.0)
    return clamp(1.0 - sev * 0.06, 0.70, 1.00)


def region_segment_factor(country_code: str, segment: str, demand: float) -> float:
    """Region and segment demand multiplier."""
    country_cfg = COUNTRY_SEGMENT_DEMAND.get(country_code.upper(), COUNTRY_SEGMENT_DEMAND["DEFAULT"])
    return demand * country_cfg.get(segment.upper(), country_cfg["DEFAULT"])


@dataclass(frozen=True)
class VehicleValuationInput:
    base_price: float
    age_years: float
    mileage_km: float
    accident_history_severity: float
    regional_demand_factor: float
    country_code: str
    segment: str


def estimate_current_value(payload: VehicleValuationInput) -> Dict[str, float]:
    """Compute current value and total depreciation.

    Coefficients and their weights:
    - 60% of signal strength comes from depreciation curve (age effect).
    - 20% from usage signal (mileage factor).
    - 10% from condition signal (accident history).
    - 10% from region/segment multiplier.
    """
    if payload.base_price < 0:
        raise ValueError("base_price must be non-negative")

    dep = depreciation_rate_factor(payload.age_years)
    mileage_f = mileage_factor(payload.age_years, payload.mileage_km)
    cond_f = condition_factor(payload.accident_history_severity)
    region_f = region_segment_factor(
        payload.country_code, payload.segment, payload.regional_demand_factor
    )

    current_value = payload.base_price * dep * mileage_f * cond_f * region_f
    total_depreciation = payload.base_price - current_value

    return {
        "current_value": round(current_value, 2),
        "total_depreciation": round(total_depreciation, 2),
        "depreciation_percent": round(total_depreciation / payload.base_price * 100, 4)
        if payload.base_price
        else 0.0,
        "age_factor": round(dep, 6),
        "mileage_factor": round(mileage_f, 6),
        "condition_factor": round(cond_f, 6),
        "region_segment_factor": round(region_f, 6),
    }


def estimate_depreciation_projection(
    payload: VehicleValuationInput,
    years: int = 5,
    annual_mileage_km: float = BASELINE_ANNUAL_KM,
) -> List[Dict[str, float]]:
    """Project market value for the next N years.

    Each projection keeps accident severity and region/segment multipliers constant
    while age and mileage increase with time.
    """
    if years <= 0:
        return []

    base = estimate_current_value(payload)
    base_value = base["current_value"]
    baseline_mileage = float(payload.mileage_km)
    prev_value = base_value

    rows: List[Dict[str, float]] = []
    for year in range(1, years + 1):
        projected_payload = VehicleValuationInput(
            base_price=payload.base_price,
            age_years=payload.age_years + year,
            mileage_km=baseline_mileage + annual_mileage_km * year,
            accident_history_severity=payload.accident_history_severity,
            regional_demand_factor=payload.regional_demand_factor,
            country_code=payload.country_code,
            segment=payload.segment,
        )
        projected = estimate_current_value(projected_payload)
        projected_value = projected["current_value"]
        yearly_loss = round(prev_value - projected_value, 2)
        rows.append(
            {
                "year": year,
                "estimated_value": projected_value,
                "annual_depreciation": max(0.0, yearly_loss),
                "cumulative_depreciation": round(base_value - projected_value, 2),
            }
        )
        prev_value = projected_value

    return rows
