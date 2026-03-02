"""Personalization layer for buyer and seller views."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class UserProfile:
    age: int
    country: str
    occupation: str
    annual_income_usd: float
    is_urban: bool = True


@dataclass(frozen=True)
class Vehicle:
    id: str
    brand: str
    model: str
    segment: str
    country: str
    price_usd: float
    mileage_km: int
    condition_grade: int
    year: int


def infer_preferred_segments(profile: UserProfile) -> List[str]:
    """Map user profile to car segment preferences."""
    age = profile.age
    country = profile.country.upper()
    occupation = (profile.occupation or "").lower()
    urban = profile.is_urban
    income = profile.annual_income_usd

    candidates = []

    if country in {"KR", "KOR"} and urban and age <= 35:
        candidates.extend(["EV", "HYBRID", "COMPACT"])
    if country in {"USA", "US"} and urban:
        candidates.extend(["TRUCK", "SUV", "SUV"])
    if country in {"UAE"} and age <= 45:
        candidates.extend(["SUV", "VAN", "LUXURY_SUV" if "lux" in occupation else "SUV"])
    if not candidates:
        candidates = ["SEDAN", "COMPACT", "SUV"]

    if "executive" in occupation or income >= 180000:
        candidates.append("LUXURY")
    if "driver" in occupation or age > 50:
        candidates.append("SUV")

    deduped = []
    seen = set()
    for seg in candidates:
        seg_u = seg.upper()
        if seg_u not in seen:
            deduped.append(seg_u)
            seen.add(seg_u)
    return deduped


def personalized_budget(profile: UserProfile) -> float:
    """
    Estimated monthly spend envelope for used car recommendations.

    Uses income elasticity by age:
    - younger users invest a higher fraction for aspiration + mobility need
    - older users use conservative fraction.
    """
    if profile.annual_income_usd <= 0:
        return 10000.0
    ratio = 0.30 if profile.age <= 30 else 0.25 if profile.age <= 50 else 0.20
    return round(profile.annual_income_usd * ratio / 12, 2)


def score_listing_for_buyer(listing: Vehicle, profile: UserProfile, region_multiplier: float) -> float:
    """Score by condition, fit score and price fit."""
    segments = set(infer_preferred_segments(profile))
    segment_match = 1.0 if listing.segment.upper() in segments else 0.65
    budget = personalized_budget(profile)
    price_fit = max(0.0, 1 - max(0.0, listing.price_usd - budget) / max(budget, 1))
    condition = listing.condition_grade / 10.0
    demand = region_multiplier
    return 0.55 * segment_match + 0.30 * condition + 0.15 * price_fit + 0.10 * demand


def recommend_buyer(
    profile: UserProfile,
    listings: Iterable[Vehicle],
    top_k: int = 6,
    region_multiplier: float = 1.0,
) -> List[Dict[str, object]]:
    ranked = []
    budget = personalized_budget(profile)
    for v in listings:
        if v.price_usd > budget * 1.25:
            continue
        score = score_listing_for_buyer(v, profile, region_multiplier)
        ranked.append((score, v))

    ranked.sort(reverse=True, key=lambda x: x[0])
    return [
        {
            "vehicle_id": v.id,
            "title": f"{v.brand} {v.model} ({v.year})",
            "price_usd": v.price_usd,
            "segment": v.segment,
            "score": round(score, 3),
            "fits_profile": score >= 0.75,
        }
        for score, v in ranked[:top_k]
    ]


def value_loss_per_1000km(purchase_price: float, current_market_value: float, mileage_delta_km: float) -> Tuple[float, float]:
    """
    Seller metric: estimated value loss per 1,000km.
    Returns (loss_total, loss_per_1000km)
    """
    delta_km = max(mileage_delta_km, 1.0)
    loss_total = max(0.0, purchase_price - current_market_value)
    return round(loss_total, 2), round(loss_total / (delta_km / 1000.0), 2)

