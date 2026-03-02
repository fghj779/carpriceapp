"""Minimal runnable API + static frontend entrypoint for carpriceapp."""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.valuation import (
    VehicleValuationInput,
    estimate_depreciation_projection,
    estimate_current_value,
)
from backend.recommendation import (
    Vehicle,
    UserProfile,
    infer_preferred_segments,
    personalized_budget,
    recommend_buyer,
    value_loss_per_1000km,
)


app = FastAPI(title="Used Car Valuation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class UserRecord(BaseModel):
    user_id: str
    age: int = Field(..., ge=16, le=120)
    country: str
    preferred_car_segments: List[str] = ["Sedan"]
    role: Literal["buyer", "seller", "both"] = "buyer"
    occupation: str = ""
    annual_income_usd: float = Field(..., ge=0)
    is_urban: bool = True


class VehicleRecord(BaseModel):
    vehicle_id: str
    vin: str = Field(..., min_length=11, max_length=17)
    make: str
    model: str
    year: int = Field(..., ge=1980, le=2100)
    mileage_km: int = Field(..., ge=0)
    condition_grade: int = Field(..., ge=1, le=10)
    segment: str
    country: str
    original_price_usd: Optional[float] = None


class CreateUserPayload(BaseModel):
    age: int = Field(..., ge=16, le=120)
    country: str = Field(..., min_length=2, max_length=3)
    preferred_car_segments: List[str] = ["Sedan"]
    role: Literal["buyer", "seller", "both"] = "buyer"
    occupation: str = ""
    annual_income_usd: float = Field(..., ge=0)
    is_urban: bool = True


class CreateVehiclePayload(BaseModel):
    vin: str = Field(..., min_length=11, max_length=17)
    make: str
    model: str
    year: int = Field(..., ge=1980, le=2100)
    mileage_km: int = Field(..., ge=0)
    condition_grade: int = Field(..., ge=1, le=10)
    segment: str
    country: str = Field(..., min_length=2, max_length=3)
    original_price_usd: Optional[float] = None


class ValuationPayload(BaseModel):
    user_id: str
    vehicle_id: str
    mode: Literal["buyer", "seller"] = "buyer"
    base_price: float = Field(..., gt=0)
    age_years: float = Field(..., ge=0)
    mileage: float = Field(..., ge=0)
    accident_history_severity: float = Field(..., ge=0, le=5)
    regional_demand_factor: float = Field(default=1.0, gt=0, le=5)
    purchase_price: Optional[float] = None
    purchase_mileage: Optional[float] = 0
    current_mileage: Optional[float] = 0


class SellerQuotePayload(BaseModel):
    country: str = Field(..., min_length=2, max_length=3)
    segment: str
    make: str = ""
    model: str = ""
    year: int = Field(..., ge=1980, le=2100)
    mileage_km: float = Field(..., ge=0)
    condition_grade: int = Field(..., ge=1, le=10)
    base_price: float = Field(..., gt=0)
    accident_history_severity: float = Field(..., ge=0, le=5)
    regional_demand_factor: float = Field(default=1.0, gt=0, le=5)
    purchase_price: Optional[float] = None
    purchase_mileage: float = Field(default=0, ge=0)
    current_mileage: Optional[float] = Field(default=None, ge=0)


class BuyerCustomInput(BaseModel):
    age: int = Field(..., ge=16, le=120)
    country: str = Field(..., min_length=2, max_length=3)
    budget_min_local: float = Field(..., ge=0)
    budget_max_local: float = Field(..., ge=0)
    currency_code: Optional[str] = None
    occupation: str = ""
    annual_income_usd: float = Field(default=0, ge=0)
    is_urban: bool = True
    preferred_car_segments: List[str] = []
    top_k: int = Field(default=6, ge=1, le=20)


class CommunityPostPayload(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    message: str = Field(default="", max_length=1000)
    mode: Literal["buyer", "seller"] = "buyer"
    country: str = Field(default="", max_length=3)
    tags: List[str] = []
    snapshot: Optional[Dict[str, Any]] = None


MARKET_TRENDS: Dict[str, List[Dict[str, float]]] = {
    "USA": [
        {"month": "Jan", "demand": 0.94, "avg_price": 21200},
        {"month": "Feb", "demand": 0.97, "avg_price": 21450},
        {"month": "Mar", "demand": 1.01, "avg_price": 21700},
        {"month": "Apr", "demand": 1.04, "avg_price": 22100},
        {"month": "May", "demand": 1.10, "avg_price": 22400},
        {"month": "Jun", "demand": 1.14, "avg_price": 23200},
    ],
    "KR": [
        {"month": "Jan", "demand": 0.96, "avg_price": 16800},
        {"month": "Feb", "demand": 0.99, "avg_price": 17000},
        {"month": "Mar", "demand": 1.05, "avg_price": 17350},
        {"month": "Apr", "demand": 1.09, "avg_price": 17800},
        {"month": "May", "demand": 1.14, "avg_price": 18120},
        {"month": "Jun", "demand": 1.18, "avg_price": 18610},
    ],
    "UAE": [
        {"month": "Jan", "demand": 0.98, "avg_price": 24800},
        {"month": "Feb", "demand": 1.02, "avg_price": 25500},
        {"month": "Mar", "demand": 1.07, "avg_price": 26200},
        {"month": "Apr", "demand": 1.10, "avg_price": 26800},
        {"month": "May", "demand": 1.16, "avg_price": 27400},
        {"month": "Jun", "demand": 1.21, "avg_price": 28100},
    ],
}

COUNTRY_CURRENCY = {
    "USA": "USD",
    "KR": "KRW",
    "KOR": "KRW",
    "UAE": "AED",
    "EU": "EUR",
    "GER": "EUR",
}

FX_TO_USD = {
    "USD": 1.0,
    "KRW": 0.00073,
    "AED": 0.272,
    "EUR": 1.08,
}


def _normalize_country_code(country: str) -> str:
    return (country or "").strip().upper()


def _normalize_currency_code(currency_code: Optional[str], country: str) -> str:
    if currency_code:
        return currency_code.strip().upper()
    return COUNTRY_CURRENCY.get(_normalize_country_code(country), "USD")


def _to_usd(amount: float, country: str, currency_code: Optional[str] = None) -> Tuple[float, str, float]:
    code = _normalize_currency_code(currency_code, country)
    rate = FX_TO_USD.get(code, 1.0)
    return round(amount * rate, 2), code, rate


def _valuation_reason_lines(
    valuation_input: VehicleValuationInput,
    valuation: Dict[str, float],
) -> List[Dict[str, float]]:
    base = valuation_input.base_price
    age_drop = round(base - base * valuation["age_factor"], 2)
    mileage_drop = round(base * valuation["age_factor"] - base * valuation["age_factor"] * valuation["mileage_factor"], 2)
    condition_drop = round(
        base * valuation["age_factor"] * valuation["mileage_factor"]
        - base
        * valuation["age_factor"]
        * valuation["mileage_factor"]
        * valuation["condition_factor"],
        2,
    )
    regional_delta = round(
        base
        * valuation["age_factor"]
        * valuation["mileage_factor"]
        * valuation["condition_factor"]
        * (valuation["region_segment_factor"] - 1.0),
        2,
    )

    return [
        {
            "factor": "연식 감가(가중치 60%)",
            "weight": 0.60,
            "impact_usd": age_drop,
            "description": f"{valuation['age_factor']:.4f} x 사용 연식 반영",
        },
        {
            "factor": "주행거리 페널티(가중치 20%)",
            "weight": 0.20,
            "impact_usd": mileage_drop,
            "description": f"{valuation['mileage_factor']:.4f} x 연식 반영값(예상 km 대비 가감)",
        },
        {
            "factor": "사고/상태 영향(가중치 10%)",
            "weight": 0.10,
            "impact_usd": condition_drop,
            "description": f"{valuation['condition_factor']:.4f} x 상태 보정",
        },
        {
            "factor": "지역·세그먼트(가중치 10%)",
            "weight": 0.10,
            "impact_usd": regional_delta,
            "description": f"{valuation['region_segment_factor']:.4f} x 최종값 조정",
        },
    ]


def _today() -> str:
    return date.today().isoformat()


def _to_user_profile(u: UserRecord) -> UserProfile:
    return UserProfile(
        age=u.age,
        country=u.country.upper(),
        occupation=u.occupation,
        annual_income_usd=u.annual_income_usd,
        is_urban=u.is_urban,
    )


def _to_vehicle_model(v: VehicleRecord) -> Vehicle:
    return Vehicle(
        id=v.vehicle_id,
        brand=v.make,
        model=v.model,
        segment=v.segment,
        country=v.country,
        price_usd=float(v.original_price_usd or 0),
        mileage_km=v.mileage_km,
        condition_grade=v.condition_grade,
        year=v.year,
    )


def _get_user(user_id: str) -> UserRecord:
    user = USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return UserRecord(**user)


def _get_vehicle(vehicle_id: str) -> VehicleRecord:
    vehicle = VEHICLES.get(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="vehicle not found")
    return VehicleRecord(**vehicle)


USERS: Dict[str, Dict[str, object]] = {}
VEHICLES: Dict[str, Dict[str, object]] = {}
VALUATIONS: List[Dict[str, object]] = []
COMMUNITY_POSTS: List[Dict[str, object]] = []


DEMO_USER_ID = str(uuid4())
DEMO_VEHICLE_ID = str(uuid4())


def _seed_data() -> None:
    if USERS:
        return

    user = UserRecord(
        user_id=DEMO_USER_ID,
        age=29,
        country="KR",
        preferred_car_segments=["COMPACT", "EV", "HYBRID"],
        role="both",
        occupation="engineer",
        annual_income_usd=54000,
        is_urban=True,
    )
    USERS[DEMO_USER_ID] = user.dict()

    vehicle_a = VehicleRecord(
        vehicle_id=DEMO_VEHICLE_ID,
        vin="KNMHD0AA0K1234567",
        make="Hyundai",
        model="Ioniq 5",
        year=2019,
        mileage_km=47000,
        condition_grade=8,
        segment="EV",
        country="KR",
        original_price_usd=32000,
    )
    vehicle_b = VehicleRecord(
        vehicle_id=str(uuid4()),
        vin="1HGCV1F34L1234588",
        make="Tesla",
        model="Model 3",
        year=2020,
        mileage_km=39000,
        condition_grade=9,
        segment="EV",
        country="USA",
        original_price_usd=42000,
    )
    vehicle_c = VehicleRecord(
        vehicle_id=str(uuid4()),
        vin="JH4KA9660MC123999",
        make="Toyota",
        model="Prado",
        year=2018,
        mileage_km=83000,
        condition_grade=7,
        segment="SUV",
        country="UAE",
        original_price_usd=36000,
    )
    for v in [vehicle_a, vehicle_b, vehicle_c]:
        VEHICLES[v.vehicle_id] = v.dict()


_seed_data()


@app.get("/", response_class=HTMLResponse)
def dashboard_home() -> HTMLResponse:
    html_file = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "date": _today()}


@app.post("/api/v1/users", response_model=UserRecord)
def create_user(payload: CreateUserPayload) -> UserRecord:
    user_id = str(uuid4())
    record = UserRecord(
        user_id=user_id,
        age=payload.age,
        country=payload.country.upper(),
        preferred_car_segments=[s.upper() for s in payload.preferred_car_segments],
        role=payload.role,
        occupation=payload.occupation,
        annual_income_usd=payload.annual_income_usd,
        is_urban=payload.is_urban,
    )
    USERS[user_id] = record.dict()
    return record


@app.get("/api/v1/users/{user_id}", response_model=UserRecord)
def get_user(user_id: str) -> UserRecord:
    return _get_user(user_id)


@app.patch("/api/v1/users/{user_id}", response_model=UserRecord)
def update_user(user_id: str, payload: CreateUserPayload) -> UserRecord:
    existing = _get_user(user_id)
    merged = existing.dict()
    merged.update(payload.dict())
    merged["country"] = merged["country"].upper()
    merged["preferred_car_segments"] = [s.upper() for s in merged["preferred_car_segments"]]
    USERS[user_id] = merged
    return UserRecord(**merged)


@app.post("/api/v1/vehicles", response_model=VehicleRecord)
def create_vehicle(payload: CreateVehiclePayload) -> VehicleRecord:
    vehicle_id = str(uuid4())
    record = VehicleRecord(
        vehicle_id=vehicle_id,
        vin=payload.vin.upper(),
        make=payload.make,
        model=payload.model,
        year=payload.year,
        mileage_km=payload.mileage_km,
        condition_grade=payload.condition_grade,
        segment=payload.segment.upper(),
        country=payload.country.upper(),
        original_price_usd=payload.original_price_usd,
    )
    if not any(v["vin"] == payload.vin.upper() for v in VEHICLES.values()):
        VEHICLES[vehicle_id] = record.dict()
    return record


@app.get("/api/v1/vehicles/{vehicle_id}", response_model=VehicleRecord)
def get_vehicle(vehicle_id: str) -> VehicleRecord:
    return _get_vehicle(vehicle_id)


@app.post("/api/v1/valuation/estimate")
def valuation_estimate(payload: ValuationPayload) -> Dict[str, object]:
    user = _get_user(payload.user_id)
    vehicle = _get_vehicle(payload.vehicle_id)

    inp = VehicleValuationInput(
        base_price=payload.base_price,
        age_years=payload.age_years,
        mileage_km=payload.mileage,
        accident_history_severity=payload.accident_history_severity,
        regional_demand_factor=payload.regional_demand_factor,
        country_code=vehicle.country,
        segment=vehicle.segment,
    )
    valuation = estimate_current_value(inp)
    profile = _to_user_profile(user)
    preferred_segments = infer_preferred_segments(profile)
    demand_series = MARKET_TRENDS.get(vehicle.country, MARKET_TRENDS["USA"])
    demand = demand_series[-1]["demand"]
    estimated_value = valuation["current_value"]

    common_payload = {
        "current_value": valuation["current_value"],
        "total_depreciation": valuation["total_depreciation"],
        "depreciation_percent": valuation["depreciation_percent"],
        "components": {
            "age_factor": valuation["age_factor"],
            "mileage_factor": valuation["mileage_factor"],
            "condition_factor": valuation["condition_factor"],
            "region_segment_factor": valuation["region_segment_factor"],
        },
        "valuation_reasons": _valuation_reason_lines(inp, valuation),
        "depreciation_projection_5y": estimate_depreciation_projection(
            inp, years=5, annual_mileage_km=15000
        ),
    }

    if payload.mode == "buyer":
        fair_low = round(max(estimated_value * 0.93, 0), 2)
        fair_high = round(estimated_value * 1.06, 2)
        risk_score = round(
            min(
                100,
                payload.accident_history_severity * 14 + max(0, 8 - (vehicle.condition_grade / 10 * 8)),
            )
        )
        tco_5y = round(
            estimated_value
            + estimated_value * 0.06 * 5
            + max(vehicle.mileage_km, 0) * 0.06,
            2,
        )
        mode_payload = {
            "fair_value_band": {"low": fair_low, "high": fair_high},
            "risk_score": risk_score,
            "total_cost_of_ownership_5y": tco_5y,
        }
    else:
        buyer_delta = max(payload.current_mileage - (payload.purchase_mileage or 0), 0)
        value_loss = value_loss_per_1000km(
            payload.purchase_price or payload.base_price,
            estimated_value,
            buyer_delta,
        )
        net_return = round(
            estimated_value
            - (estimated_value * 0.025)
            - (estimated_value * max(0, 1 - demand)),
            2,
        )
        time_to_sell_days = max(7, int(65 / max(demand, 0.2)))
        mode_payload = {
            "net_return": net_return,
            "time_to_sell_days": time_to_sell_days,
            "value_retention_tips": [
                "Bundle service history and repair invoices with listing photos.",
                "Refresh tires/wheels photos first; visual condition boosts lead response by 6-8%.",
                "List on weekdays for higher inspection conversion in KR/USA, weekends in UAE.",
            ],
            "value_loss": {
                "total": value_loss[0],
                "per_1000km": value_loss[1],
            },
        }

    valuation_id = str(uuid4())
    stored = {
        "valuation_id": valuation_id,
        "user_id": user.user_id,
        "vehicle_id": vehicle.vehicle_id,
        "mode": payload.mode,
        "created_at": _today(),
        "request": payload.dict(),
        "response": {"common": common_payload, "mode_payload": mode_payload},
    }
    VALUATIONS.append(stored)

    return {
        "valuation_id": valuation_id,
        "user": _get_user(payload.user_id),
        "vehicle": _get_vehicle(payload.vehicle_id),
        "preferred_segments": preferred_segments,
        "country_demand": demand,
        "common": common_payload,
        "mode": payload.mode,
        payload.mode: mode_payload,
    }


@app.post("/api/v1/valuation/seller-quote")
def valuation_seller_quote(payload: SellerQuotePayload) -> Dict[str, object]:
    country = _normalize_country_code(payload.country)
    demand_series = MARKET_TRENDS.get(country, MARKET_TRENDS["USA"])
    demand = demand_series[-1]["demand"]
    current_year = date.today().year
    age_years = max(current_year - payload.year, 0)
    mileage_km = (
        payload.current_mileage
        if payload.current_mileage is not None
        else payload.mileage_km
    )
    mileage_km = max(mileage_km, payload.mileage_km)

    inp = VehicleValuationInput(
        base_price=payload.base_price,
        age_years=float(age_years),
        mileage_km=mileage_km,
        accident_history_severity=payload.accident_history_severity,
        regional_demand_factor=payload.regional_demand_factor * demand,
        country_code=country,
        segment=payload.segment.upper(),
    )
    valuation = estimate_current_value(inp)

    purchase_price = payload.purchase_price or payload.base_price
    mileage_delta = max(mileage_km - payload.purchase_mileage, 0)
    value_loss = value_loss_per_1000km(purchase_price, valuation["current_value"], mileage_delta)
    net_return = round(
        valuation["current_value"]
        - (valuation["current_value"] * 0.025)
        - (valuation["current_value"] * max(0, 1 - demand)),
        2,
    )

    return {
        "mode": "seller",
        "input": {
            "country": country,
            "segment": payload.segment.upper(),
            "make": payload.make,
            "model": payload.model,
            "year": payload.year,
            "mileage_km": mileage_km,
        },
        "market": {
            "demand_index": demand,
            "regional_demand_factor": inp.regional_demand_factor,
        },
        "valuation": {
            "estimated_sale_value": valuation["current_value"],
            "total_depreciation": valuation["total_depreciation"],
            "depreciation_percent": valuation["depreciation_percent"],
            "components": {
                "age_factor": valuation["age_factor"],
                "mileage_factor": valuation["mileage_factor"],
                "condition_factor": valuation["condition_factor"],
                "region_segment_factor": valuation["region_segment_factor"],
            },
            "valuation_reasons": _valuation_reason_lines(inp, valuation),
            "depreciation_projection_5y": estimate_depreciation_projection(
                inp, years=5, annual_mileage_km=15000
            ),
        },
        "net_return_estimate": net_return,
        "time_to_sell_days": max(4, int(70 / max(demand, 0.2))),
        "value_loss": {
            "purchase_price": purchase_price,
            "mileage_delta_km": mileage_delta,
            "loss_total": value_loss[0],
            "per_1000km": value_loss[1],
        },
        "value_retention_tips": [
            "정비 이력, 사고 이력, 오일 교체 증빙을 한 번에 업로드하면 협상율이 좋아집니다.",
            "정면 및 실내 사진 품질을 확보하고 미세한 흠집은 개별 노출해 신뢰도를 높이세요.",
            "계약 전 차량 점검 리포트를 제공하면 구매 반응 속도가 향상됩니다.",
        ],
    }


@app.post("/api/v1/recommendations/buyer/custom")
def recommendation_buyer_custom(payload: BuyerCustomInput) -> Dict[str, object]:
    if payload.budget_min_local > payload.budget_max_local:
        raise HTTPException(status_code=400, detail="budget_min_local must be <= budget_max_local")

    country = _normalize_country_code(payload.country)
    budget_min_usd, used_currency, fx_rate_min = _to_usd(
        payload.budget_min_local, country, payload.currency_code
    )
    budget_max_usd, _, fx_rate_max = _to_usd(
        payload.budget_max_local, country, payload.currency_code
    )
    fx_rate = max(fx_rate_min, fx_rate_max)
    if fx_rate <= 0:
        fx_rate = 1.0

    profile = UserProfile(
        age=payload.age,
        country=country,
        occupation=payload.occupation,
        annual_income_usd=payload.annual_income_usd,
        is_urban=payload.is_urban,
    )
    demand_series = MARKET_TRENDS.get(country, MARKET_TRENDS["USA"])
    demand = demand_series[-1]["demand"]

    if payload.preferred_car_segments:
        profile_segments = [s.upper() for s in payload.preferred_car_segments]
        preferred = list(dict.fromkeys(profile_segments))
    else:
        preferred = infer_preferred_segments(profile)

    all_listings = [_to_vehicle_model(VehicleRecord(**v)) for v in VEHICLES.values()]
    filtered = [x for x in all_listings if x.country.upper() == country]

    results = []
    for rec in recommend_buyer(
        profile,
        filtered,
        top_k=payload.top_k,
        region_multiplier=demand,
        budget_cap=budget_max_usd,
    ):
        target = next((v for v in VEHICLES.values() if v["vehicle_id"] == rec["vehicle_id"]), None)
        if not target:
            continue

        listing_age = max(date.today().year - target["year"], 0)
        accident_severity = max(0.0, 5.0 - (target["condition_grade"] / 2.0))
        valuation_input = VehicleValuationInput(
            base_price=float(target["original_price_usd"] or 0),
            age_years=float(listing_age),
            mileage_km=target["mileage_km"],
            accident_history_severity=accident_severity,
            regional_demand_factor=demand,
            country_code=target["country"],
            segment=target["segment"],
        )
        current_value = estimate_current_value(valuation_input)["current_value"]
        projected = estimate_depreciation_projection(
            valuation_input, years=5, annual_mileage_km=15000
        )
        current_value = float(current_value)
        fair_low = round(max(current_value * 0.93, 0), 2)
        fair_high = round(current_value * 1.06, 2)

        results.append(
            {
                **rec,
                "make": target["make"],
                "model": target["model"],
                "year": target["year"],
                "current_value": current_value,
                "depreciation_projection_5y": projected,
                "fair_value_band": {"low": fair_low, "high": fair_high},
                "fits_profile": any(seg == target["segment"].upper() for seg in preferred),
                "country": target["country"],
            }
        )

    return {
        "user_id": f"temp-{_normalize_country_code(country)}-{payload.age}",
        "country": country,
        "budget_input": {
            "min_local": payload.budget_min_local,
            "max_local": payload.budget_max_local,
            "currency": used_currency,
            "usd_rate": fx_rate,
        },
        "budget_usd": {"min": budget_min_usd, "max": budget_max_usd},
        "market_demand": demand,
        "personalized_budget": personalized_budget(profile),
        "preferred_segments": preferred,
        "recommendations": results,
        "count": len(results),
    }


@app.get("/api/v1/recommendations/buyer")
def recommendation_buyer(user_id: str, top_k: int = 5) -> Dict[str, object]:
    user = _get_user(user_id)
    profile = _to_user_profile(user)
    demand_series = MARKET_TRENDS.get(user.country, MARKET_TRENDS["USA"])
    demand = demand_series[-1]["demand"]

    all_listings = [_to_vehicle_model(VehicleRecord(**v)) for v in VEHICLES.values()]
    filtered = [x for x in all_listings if x.country.upper() == user.country]
    results = recommend_buyer(profile, filtered, top_k=top_k, region_multiplier=demand)

    enhanced = []
    for rec in results:
        target = next((v for v in VEHICLES.values() if v["vehicle_id"] == rec["vehicle_id"]), None)
        if not target:
            continue
        listing_age = max(date.today().year - target["year"], 0)
        accident_severity = max(0.0, 5.0 - (target["condition_grade"] / 2.0))
        valuation_input = VehicleValuationInput(
            base_price=float(target["original_price_usd"] or 0),
            age_years=float(listing_age),
            mileage_km=target["mileage_km"],
            accident_history_severity=accident_severity,
            regional_demand_factor=demand,
            country_code=target["country"],
            segment=target["segment"],
        )
        current_value = estimate_current_value(valuation_input)["current_value"]
        projected = estimate_depreciation_projection(
            valuation_input, years=5, annual_mileage_km=15000
        )
        rec["depreciation_projection_5y"] = projected
        current_value = float(current_value)
        rec["fair_value_band"] = {
            "low": round(max(current_value * 0.93, 0), 2),
            "high": round(current_value * 1.06, 2),
        }
        enhanced.append(rec)

    return {
        "user_id": user.user_id,
        "personalized_budget": personalized_budget(profile),
        "country": user.country,
        "country_demand_multiplier": demand,
        "preferred_segments": infer_preferred_segments(profile),
        "recommendations": enhanced,
        "count": len(enhanced),
    }


@app.get("/api/v1/recommendations/seller/{vehicle_id}")
def recommendation_seller(
    vehicle_id: str,
    user_id: str,
    purchase_price: float,
    purchase_mileage: float = 0,
    current_mileage: float = 0,
) -> Dict[str, object]:
    user = _get_user(user_id)
    vehicle = _get_vehicle(vehicle_id)
    demand_series = MARKET_TRENDS.get(user.country, MARKET_TRENDS["USA"])
    demand = demand_series[-1]["demand"]
    current_age_years = max((current_mileage or 0) / 20000, 0.5)

    estimated = valuation_estimate(
        ValuationPayload(
            user_id=user_id,
            vehicle_id=vehicle_id,
            mode="seller",
            base_price=float(vehicle.original_price_usd or 0) if vehicle.original_price_usd else 12000,
            age_years=current_age_years,
            mileage=current_mileage or 0,
            accident_history_severity=max(0, 5 - vehicle.condition_grade / 2),
            regional_demand_factor=1.0,
            purchase_price=purchase_price,
            purchase_mileage=purchase_mileage,
            current_mileage=current_mileage,
        )
    )["seller"]

    corridor_low = round(estimated["net_return"] * 0.94, 2)
    corridor_high = round(estimated["net_return"] * 1.08, 2)

    return {
        "user_id": user_id,
        "vehicle_id": vehicle_id,
        "expected_net_return_range": {"low": corridor_low, "high": corridor_high},
        "time_to_sell_days": estimated["time_to_sell_days"],
        "value_retention_tips": estimated["value_retention_tips"],
        "value_loss": estimated["value_loss"],
        "market_demand": demand,
        "country": user.country,
    }


@app.get("/api/v1/demo/bootstrap")
def demo_bootstrap() -> Dict[str, object]:
    country = USERS[DEMO_USER_ID]["country"]
    profile = _to_user_profile(UserRecord(**USERS[DEMO_USER_ID]))
    return {
        "user": USERS[DEMO_USER_ID],
        "listings": [v for v in VEHICLES.values() if v["country"] == country],
        "vehicle_id": DEMO_VEHICLE_ID,
        "personalized_budget": personalized_budget(profile),
        "owned_vehicle": {
            "purchase_price": 40000,
            "purchase_mileage": 22000,
            "current_mileage": 47000,
        },
    }


@app.post("/api/v1/community/posts")
def community_post_create(payload: CommunityPostPayload) -> Dict[str, object]:
    post_id = str(uuid4())
    country = payload.country.strip().upper() if payload.country else ""
    post = {
        "post_id": post_id,
        "created_at": _today(),
        "title": payload.title.strip(),
        "message": payload.message.strip(),
        "mode": payload.mode,
        "country": country,
        "tags": [tag.strip().upper() for tag in payload.tags if tag.strip()],
        "snapshot": payload.snapshot or {},
    }
    COMMUNITY_POSTS.insert(0, post)
    if len(COMMUNITY_POSTS) > 200:
        COMMUNITY_POSTS.pop()
    return post


@app.get("/api/v1/community/posts")
def community_post_list(
    mode: Optional[Literal["buyer", "seller"]] = None,
    country: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, object]:
    posts = COMMUNITY_POSTS
    if mode:
        posts = [p for p in posts if p["mode"] == mode]
    if country:
        normalized_country = country.strip().upper()
        posts = [p for p in posts if p["country"] == normalized_country]
    selected = posts[:limit]
    return {"count": len(selected), "posts": selected}
