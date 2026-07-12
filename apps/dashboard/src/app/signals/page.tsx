'use client';

import { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Signal {
  signal_id: string;
  signal_type: string;
  direction: string;
  score: number;
  confidence: number;
  generated_at: string;
  component_scores: Record<string, number>;
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/v1/signals?page_size=50`)
      .then((r) => r.json())
      .then((d) => setSignals(d.items || []))
      .catch(() => {});
  }, []);

  const chartOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: signals.map((s) => s.signal_type.replace(/_/g, ' ')),
      axisLabel: { color: '#94a3b8', rotate: 30 },
    },
    yAxis: { type: 'value', max: 1, axisLabel: { color: '#94a3b8' } },
    series: [
      { name: 'Score', type: 'bar', data: signals.map((s) => s.score), itemStyle: { color: '#38bdf8' } },
      { name: 'Confidence', type: 'bar', data: signals.map((s) => s.confidence), itemStyle: { color: '#a78bfa' } },
    ],
  };

  return (
    <div>
      <h1>Market Signals</h1>
      <p style={{ color: '#94a3b8' }}>Explainable signals with component scores and evidence provenance.</p>
      {signals.length > 0 && (
        <div style={{ background: '#1e293b', borderRadius: '8px', padding: '1rem', marginBottom: '2rem' }}>
          <ReactECharts option={chartOption} style={{ height: 300 }} />
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {signals.map((signal) => (
          <div key={signal.signal_id} style={{ background: '#1e293b', borderRadius: '8px', padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, color: '#f472b6' }}>{signal.signal_type.replace(/_/g, ' ')}</h3>
              <span style={{
                padding: '0.25rem 0.75rem',
                borderRadius: '4px',
                fontSize: '0.75rem',
                background: signal.direction === 'negative' ? '#7f1d1d' : '#14532d',
                color: signal.direction === 'negative' ? '#fca5a5' : '#86efac',
              }}>
                {signal.direction}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '2rem', marginTop: '0.75rem', fontSize: '0.875rem' }}>
              <span>Score: <strong>{signal.score.toFixed(3)}</strong></span>
              <span>Confidence: <strong>{signal.confidence.toFixed(3)}</strong></span>
              <span>{new Date(signal.generated_at).toLocaleString()}</span>
            </div>
            {signal.component_scores && (
              <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {Object.entries(signal.component_scores).map(([key, val]) => (
                  <span key={key} style={{ background: '#334155', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                    {key}: {val.toFixed(2)}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
