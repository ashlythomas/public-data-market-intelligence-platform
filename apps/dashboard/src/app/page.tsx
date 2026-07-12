'use client';

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DashboardStats {
  documents: number;
  events: number;
  signals: number;
  narratives: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({ documents: 0, events: 0, signals: 0, narratives: 0 });
  const [health, setHealth] = useState<string>('checking...');

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then((d) => setHealth(d.status))
      .catch(() => setHealth('unavailable'));

    Promise.all([
      fetch(`${API_URL}/v1/documents?page_size=1`).then((r) => r.json()),
      fetch(`${API_URL}/v1/events?page_size=1`).then((r) => r.json()),
      fetch(`${API_URL}/v1/signals?page_size=1`).then((r) => r.json()),
      fetch(`${API_URL}/v1/narratives?page_size=1`).then((r) => r.json()),
    ]).then(([docs, events, signals, narratives]) => {
      setStats({
        documents: docs.total ?? 0,
        events: events.total ?? 0,
        signals: signals.total ?? 0,
        narratives: narratives.total ?? 0,
      });
    }).catch(() => {});
  }, []);

  const cards = [
    { label: 'Documents', value: stats.documents, color: '#38bdf8' },
    { label: 'Events', value: stats.events, color: '#a78bfa' },
    { label: 'Signals', value: stats.signals, color: '#f472b6' },
    { label: 'Narratives', value: stats.narratives, color: '#34d399' },
  ];

  return (
    <div>
      <h1 style={{ marginBottom: '0.5rem' }}>Analyst Dashboard</h1>
      <p style={{ color: '#94a3b8', marginBottom: '2rem' }}>
        API status: <span style={{ color: health === 'healthy' ? '#34d399' : '#f87171' }}>{health}</span>
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        {cards.map((card) => (
          <div key={card.label} style={{ background: '#1e293b', borderRadius: '8px', padding: '1.5rem', borderLeft: `4px solid ${card.color}` }}>
            <div style={{ color: '#94a3b8', fontSize: '0.875rem' }}>{card.label}</div>
            <div style={{ fontSize: '2rem', fontWeight: 700, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>
      <div style={{ background: '#1e293b', borderRadius: '8px', padding: '1.5rem' }}>
        <h2 style={{ marginTop: 0 }}>Quick Search</h2>
        <p style={{ color: '#94a3b8' }}>Search public market intelligence data from Federal Reserve, GDELT, SEC EDGAR, and more.</p>
        <a href="/search" style={{ display: 'inline-block', marginTop: '1rem', padding: '0.75rem 1.5rem', background: '#38bdf8', color: '#0f172a', borderRadius: '6px', textDecoration: 'none', fontWeight: 600 }}>
          Open Search
        </a>
      </div>
    </div>
  );
}
