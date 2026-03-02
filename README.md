# Used Car Valuation & Marketplace (carpriceapp)

This repository contains a technical baseline for a dual-mode used-car valuation application.
It includes:

- PostgreSQL schema for users, vehicles, and market data
- Python valuation engine and personalization utilities
- React buyer/seller dashboard component

## Database schema

`db/schema.sql` defines:

- `users`: age, country, preferred car segments, role
- `vehicles`: VIN, make, model, year, mileage, and condition grade
- `market_data`: regional price trends and brand-level depreciation constants
- `valuations`: valuation history per request

See schema details in `db/schema.sql`.

## Valuation logic

`backend/valuation.py` implements:

- Piece-wise age depreciation:
  - 15% for first year
  - 10% for years after the first
- Mileage factor and accident-based condition factor
- Regional + segment adjustment (e.g., UAE SUV bias, Korea compact bias)
- Returns both:
  - `current_value`
  - `total_depreciation`

## API contracts (summary)

### User
- `POST /api/v1/users`  
  Create a user profile.
- `PATCH /api/v1/users/{user_id}`  
  Update profile data (age, country, role, preferred segments, occupation, income).

### Vehicles
- `POST /api/v1/vehicles`  
  Register or upsert a vehicle by VIN with metadata.
- `GET /api/v1/vehicles/{vehicle_id}`  
  Fetch canonical vehicle record.

### Valuation
- `POST /api/v1/valuation/estimate`  
  Estimate value and depreciation for buyer/seller context.

Request body:
- `user_id`
- `vehicle_id`
- `mode: buyer|seller`
- `base_price`
- `age_years`
- `mileage`
- `accident_history_severity`
- `regional_demand_factor`

Response includes:
- `common`: `current_value`, `total_depreciation`, `depreciation_percent`, component factors
- buyer extras: fair-value band and risk signals
- seller extras: value-loss guidance and market-timing signal

### Recommendations
- `GET /api/v1/recommendations/buyer`  
  Personalized listing candidates for buyer mode.
- `GET /api/v1/recommendations/seller/{vehicle_id}`  
  Seller-oriented recommendations (time-to-sell + target asking corridor).
- `GET /api/v1/market/{country}/trends`  
  Returns trend series for chart rendering.

## Frontend

`frontend/UsedCarDashboard.jsx` provides mode switching between:
- Buyer View:
  - Best-value recommendations
  - Personalized budget from profile
  - Regional price trend chart
- Seller View:
  - Value loss tracker (per 1,000km)
  - Optimal selling time from demand trend

