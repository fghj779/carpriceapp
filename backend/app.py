"""Minimal runnable API + static frontend entrypoint for carpriceapp."""

from datetime import date
from pathlib import Path
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.valuation import (
    VehicleValuationInput,
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


@app.get("/api/v1/market/{country_code}/trends")
def market_trends(country_code: str) -> Dict[str, object]:
    country = country_code.upper()
    data = MARKET_TRENDS.get(country, MARKET_TRENDS["USA"])
    return {
        "country": country,
        "snapshot_date": _today(),
        "trend": data,
        "demand_index_latest": data[-1]["demand"],
    }


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


@app.get("/api/v1/recommendations/buyer")
def recommendation_buyer(user_id: str, top_k: int = 5) -> Dict[str, object]:
    user = _get_user(user_id)
    profile = _to_user_profile(user)
    demand_series = MARKET_TRENDS.get(user.country, MARKET_TRENDS["USA"])
    demand = demand_series[-1]["demand"]

    all_listings = [_to_vehicle_model(VehicleRecord(**v)) for v in VEHICLES.values()]
    filtered = [x for x in all_listings if x.country.upper() == user.country]
    results = recommend_buyer(profile, filtered, top_k=top_k, region_multiplier=demand)

    return {
        "user_id": user.user_id,
        "personalized_budget": personalized_budget(profile),
        "country": user.country,
        "country_demand_multiplier": demand,
        "preferred_segments": infer_preferred_segments(profile),
        "recommendations": results,
        "count": len(results),
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
        "market_trend": MARKET_TRENDS.get(country, MARKET_TRENDS["USA"]),
        "personalized_budget": personalized_budget(profile),
        "owned_vehicle": {
            "purchase_price": 40000,
            "purchase_mileage": 22000,
            "current_mileage": 47000,
        },
    }
