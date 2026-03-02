import React, { useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const SAMPLE_TREND = [
  { month: 'Jan', demand: 0.92, avgPrice: 21400 },
  { month: 'Feb', demand: 0.96, avgPrice: 21800 },
  { month: 'Mar', demand: 0.98, avgPrice: 21600 },
  { month: 'Apr', demand: 1.02, avgPrice: 22200 },
  { month: 'May', demand: 1.08, avgPrice: 23100 },
  { month: 'Jun', demand: 1.12, avgPrice: 23600 },
];

function toMoney(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(value);
}

function budgetFromProfile(profile) {
  if (!profile?.annualIncomeUsd) return 12000;
  const ratio = profile.age <= 30 ? 0.30 : profile.age <= 50 ? 0.24 : 0.20;
  return Math.round((profile.annualIncomeUsd * ratio) / 12);
}

function inferSegments(profile) {
  const country = profile?.country || '';
  const age = profile?.age || 30;
  const urban = profile?.isUrban !== false;

  if ((country === 'KR' || country === 'EU') && urban && age <= 35) {
    return ['EV', 'HYBRID', 'COMPACT'];
  }
  if (country === 'USA' && age <= 45) {
    return ['TRUCK', 'SUV', 'PICKUP'];
  }
  if (country === 'UAE') {
    return ['SUV', 'VAN', 'LUXURY'];
  }
  return ['SEDAN', 'SUV', 'COMPACT'];
}

function pickBestWindow(trend) {
  const best = trend.reduce((a, b) => (b.demand > a.demand ? b : a), trend[0]);
  const idx = trend.findIndex((x) => x.month === best.month);
  return {
    month: best.month,
    action: idx <= 1 ? 'List now' : `Consider waiting ${idx - 1} month(s)`,
    demand: best.demand,
  };
}

export default function UsedCarDashboard({ userProfile, listings = [], marketTrend = SAMPLE_TREND, ownedVehicle }) {
  const [mode, setMode] = useState('buyer');
  const budget = useMemo(() => budgetFromProfile(userProfile), [userProfile]);
  const preferredSegments = useMemo(() => inferSegments(userProfile), [userProfile]);

  const buyerItems = useMemo(() => {
    return listings
      .filter((x) => preferredSegments.includes(x.segment))
      .filter((x) => x.priceUsd <= budget * 1.25)
      .sort((a, b) => a.priceUsd - b.priceUsd)
      .slice(0, 5)
      .map((x) => ({
        ...x,
        label: `${x.make} ${x.model} ${x.year}`,
      }));
  }, [listings, preferredSegments, budget]);

  const valueLoss = useMemo(() => {
    if (!ownedVehicle) return null;
    const {
      purchasePrice = 0,
      currentValue = 0,
      currentMileage = 0,
      purchaseMileage = 0,
    } = ownedVehicle;
    const deltaKm = Math.max(1, currentMileage - purchaseMileage);
    const loss = Math.max(0, purchasePrice - currentValue);
    return {
      totalLoss: loss,
      per1000Km: loss / (deltaKm / 1000),
    };
  }, [ownedVehicle]);

  const marketTip = useMemo(() => pickBestWindow(marketTrend), [marketTrend]);

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <h2 style={styles.title}>Used Car Valuation Dashboard</h2>
        <div style={styles.tabs}>
          <button style={mode === 'buyer' ? styles.activeTab : styles.tab} onClick={() => setMode('buyer')}>
            Buyer Mode
          </button>
          <button style={mode === 'seller' ? styles.activeTab : styles.tab} onClick={() => setMode('seller')}>
            Seller Mode
          </button>
        </div>
      </header>

      <section style={styles.panel}>
        <p style={styles.meta}>
          Budget cap: {toMoney(budget)} · Country: {userProfile?.country || 'Unknown'}
        </p>
        <p style={styles.meta}>Preference: {preferredSegments.join(', ')}</p>
      </section>

      {mode === 'buyer' ? (
        <section style={styles.grid}>
          <article style={styles.card}>
            <h3>Best Value Recommendations</h3>
            {buyerItems.length === 0 ? (
              <p>No matches under current personalized budget.</p>
            ) : (
              buyerItems.map((car) => (
                <div key={car.id} style={styles.listItem}>
                  <span>
                    {car.label} · {toMoney(car.priceUsd)}
                  </span>
                  <strong>{car.mileageKm?.toLocaleString()} km</strong>
                </div>
              ))
            )}
          </article>
          <article style={styles.card}>
            <h3>Regional Price Trend</h3>
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={marketTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(v) => toMoney(v)} />
                <Line type="monotone" dataKey="avgPrice" stroke="#1d4ed8" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </article>
        </section>
      ) : (
        <section style={styles.grid}>
          <article style={styles.card}>
            <h3>Value Loss Tracker</h3>
            {valueLoss ? (
              <>
                <p>Total value loss: {toMoney(valueLoss.totalLoss)}</p>
                <p>Loss per 1,000 km: {toMoney(valueLoss.per1000Km)}</p>
              </>
            ) : (
              <p>Provide purchase and current valuation to compute value loss.</p>
            )}
          </article>
          <article style={styles.card}>
            <h3>Optimal Selling Time</h3>
            <p>
              {marketTip.action} to hit the strongest demand window ({marketTip.month}, demand {marketTip.demand.toFixed(2)}).
            </p>
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={marketTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="demand" stroke="#059669" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </article>
        </section>
      )}
    </main>
  );
}

const styles = {
  page: {
    background: 'linear-gradient(140deg, #eff6ff, #ecfeff)',
    minHeight: '100vh',
    padding: 24,
    fontFamily: 'Inter, Arial, sans-serif',
    color: '#0f172a',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  title: { margin: 0 },
  tabs: { display: 'flex', gap: 8 },
  tab: {
    border: '1px solid #cbd5e1',
    background: '#ffffff',
    color: '#0f172a',
    padding: '8px 12px',
    borderRadius: 8,
  },
  activeTab: {
    border: '1px solid #1d4ed8',
    background: '#dbeafe',
    color: '#1d4ed8',
    padding: '8px 12px',
    borderRadius: 8,
  },
  panel: {
    marginBottom: 16,
    background: '#ffffff',
    border: '1px solid #d1d5db',
    borderRadius: 10,
    padding: 12,
  },
  meta: { margin: '4px 0' },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  card: {
    border: '1px solid #d1d5db',
    borderRadius: 10,
    background: '#ffffff',
    padding: 12,
  },
  listItem: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #e5e7eb',
  },
};

