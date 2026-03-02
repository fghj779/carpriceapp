# carpriceapp

Runnable baseline for a dual-mode used-car valuation app (Buyer/Seller).

## What’s in this repo

- `db/schema.sql`: PostgreSQL schema (users, vehicles, market data, valuations)
- `backend/valuation.py`: valuation engine and depreciation calculation
- `backend/recommendation.py`: personalization and recommendation helpers
- `backend/app.py`: FastAPI API for valuation + recommendations
- `backend/requirements.txt`: Python dependencies
- `backend/run.sh`: local API start script
- `frontend/index.html`: runnable React dashboard (zero build setup)

## Quick local run

1. Create and activate your virtual environment.
2. Install API dependencies:

```bash
python3 -m pip install -r backend/requirements.txt
```

3. Start the backend:

```bash
bash backend/run.sh
```

4. Open dashboard:

```
http://127.0.0.1:8000
```

## Useful endpoints

- `GET /health` → service status
- `GET /` → React dashboard page
- `POST /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/vehicles`
- `GET /api/v1/vehicles/{vehicle_id}`
- `POST /api/v1/valuation/estimate`
- `GET /api/v1/recommendations/buyer?user_id=<id>&top_k=6`
- `GET /api/v1/recommendations/seller/{vehicle_id}?user_id=<id>&purchase_price=...`
- `GET /api/v1/market/{country}/trends`
- `GET /api/v1/demo/bootstrap` → preloaded demo payload for frontend
- `GET /docs` → interactive OpenAPI docs

## Default seeded data

- User and listing records are preloaded to make the demo run immediately.
- The dashboard fetches `/api/v1/demo/bootstrap` on load and connects to recommendation endpoints directly.

## Notes

- The frontend is a lightweight React page loaded from CDN and rendered with Babel in-browser.
- For production use, move frontend to a compiled React app and replace CDN/Babel with a bundler.

