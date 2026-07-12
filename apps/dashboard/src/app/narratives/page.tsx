'use client';

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Narrative {
  narrative_id: string;
  title: string;
  lifecycle_state: string;
  velocity_score: number;
  sentiment_score: number;
  last_updated_at: string;
}

const STATE_COLORS: Record<string, string> = {
  emerging: '#38bdf8',
  accelerating: '#fbbf24',
  established: '#34d399',
  declining: '#f87171',
  dormant: '#64748b',
};

export default function NarrativesPage() {
  const [narratives, setNarratives] = useState<Narrative[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/v1/narratives?page_size=50`)
      .then((r) => r.json())
      .then((d) => setNarratives(d.items || []))
      .catch(() => {});
  }, []);

  return (
    <div>
      <h1>Narratives</h1>
      <p style={{ color: '#94a3b8' }}>Temporally evolving clusters of related events with lifecycle metrics.</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {narratives.map((narrative) => (
          <div key={narrative.narrative_id} style={{ background: '#1e293b', borderRadius: '8px', padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <h3 style={{ margin: 0 }}>{narrative.title}</h3>
              <span style={{
                padding: '0.25rem 0.75rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                background: STATE_COLORS[narrative.lifecycle_state] || '#64748b',
                color: '#0f172a',
                fontWeight: 600,
              }}>
                {narrative.lifecycle_state}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '2rem', marginTop: '0.75rem', fontSize: '0.875rem', color: '#94a3b8' }}>
              <span>Velocity: {narrative.velocity_score.toFixed(2)}</span>
              <span>Sentiment: {narrative.sentiment_score.toFixed(2)}</span>
              <span>Updated: {new Date(narrative.last_updated_at).toLocaleString()}</span>
            </div>
          </div>
        ))}
        {narratives.length === 0 && (
          <p style={{ color: '#64748b' }}>No narratives yet. Run seed data to populate sample narratives.</p>
        )}
      </div>
    </div>
  );
}
