CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE user_role AS ENUM ('buyer', 'seller', 'both');
CREATE TYPE segment_type AS ENUM ('EV', 'Hybrid', 'Compact', 'Sedan', 'SUV', 'Truck', 'Van', 'Coupe', 'Hatchback');
CREATE TYPE valuation_mode AS ENUM ('buyer', 'seller');

CREATE TABLE countries (
    country_code CHAR(2) PRIMARY KEY,
    country_name TEXT NOT NULL,
    tax_factor NUMERIC(6,4) NOT NULL DEFAULT 1.0000,
    fuel_cost_index NUMERIC(6,4) NOT NULL DEFAULT 1.0000,
    demand_bias_usd_index NUMERIC(6,4) NOT NULL DEFAULT 1.0000
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    age SMALLINT NOT NULL CHECK (age BETWEEN 16 AND 120),
    country_code CHAR(2) NOT NULL REFERENCES countries(country_code),
    preferred_car_segments segment_type[] NOT NULL DEFAULT ARRAY['Sedan']::segment_type[],
    role user_role NOT NULL DEFAULT 'buyer',
    occupation TEXT,
    annual_income_usd NUMERIC(14,2) NOT NULL DEFAULT 0,
    is_urban BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE vehicles (
    vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vin CHAR(17) NOT NULL UNIQUE CHECK (char_length(vin) = 17),
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year BETWEEN 1980 AND 2100),
    mileage_km INTEGER NOT NULL CHECK (mileage_km >= 0),
    condition_grade INTEGER NOT NULL CHECK (condition_grade BETWEEN 1 AND 10),
    segment segment_type NOT NULL,
    country_code CHAR(2) NOT NULL REFERENCES countries(country_code),
    seller_user_id UUID REFERENCES users(user_id),
    original_price_usd NUMERIC(14,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE market_data (
    market_data_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code CHAR(2) NOT NULL REFERENCES countries(country_code),
    brand TEXT NOT NULL,
    segment segment_type NOT NULL,
    snapshot_month DATE NOT NULL,
    regional_price_index NUMERIC(12,6) NOT NULL DEFAULT 1.000000,
    avg_list_price_usd NUMERIC(14,2) NOT NULL,
    depreciation_rate_year1 NUMERIC(6,4) NOT NULL DEFAULT 0.1500,
    depreciation_rate_after_year1 NUMERIC(6,4) NOT NULL DEFAULT 0.1000,
    demand_index NUMERIC(8,4) NOT NULL DEFAULT 1.0000,
    source TEXT NOT NULL DEFAULT 'market_feed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (country_code, brand, segment, snapshot_month)
);

CREATE TABLE valuations (
    valuation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    vehicle_id UUID NOT NULL REFERENCES vehicles(vehicle_id),
    mode valuation_mode NOT NULL,
    base_price NUMERIC(14,2) NOT NULL,
    age_years NUMERIC(5,2) NOT NULL,
    mileage INTEGER NOT NULL,
    accident_history_severity NUMERIC(3,1) NOT NULL CHECK (accident_history_severity BETWEEN 0 AND 5),
    regional_demand_factor NUMERIC(6,4) NOT NULL DEFAULT 1.0000,
    current_market_value NUMERIC(14,2) NOT NULL,
    total_depreciation NUMERIC(14,2) NOT NULL,
    recommendation_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE accident_events (
    accident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    severity INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 5),
    occurred_at DATE NOT NULL,
    description TEXT,
    cost_usd NUMERIC(14,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_country ON users(country_code);
CREATE INDEX idx_vehicles_make_model_year ON vehicles(make, model, year);
CREATE INDEX idx_vehicles_segment ON vehicles(segment);
CREATE INDEX idx_vehicles_country ON vehicles(country_code);
CREATE INDEX idx_market_data_region_brand_segment ON market_data(country_code, brand, segment, snapshot_month);
CREATE INDEX idx_val_user_mode ON valuations(user_id, mode, created_at DESC);
