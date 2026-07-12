'use client';

import { useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SearchResult {
  id: string;
  type: string;
  title: string | null;
  snippet: string | null;
  score: number;
  source_id: string | null;
  published_at: string | null;
}

export default function SearchPage() {
  const [query, setQuery] = useState('Federal Reserve inflation');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [queryTime, setQueryTime] = useState<number | null>(null);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/v1/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, page: 1, page_size: 20 }),
      });
      const data = await response.json();
      setResults(data.results || []);
      setQueryTime(data.query_time_ms);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Document Search</h1>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          style={{ flex: 1, padding: '0.75rem', background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', color: '#e2e8f0', fontSize: '1rem' }}
          placeholder="Search topics, entities, events..."
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          style={{ padding: '0.75rem 1.5rem', background: '#38bdf8', color: '#0f172a', border: 'none', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
      {queryTime !== null && (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>{results.length} results in {queryTime.toFixed(0)}ms</p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {results.map((result) => (
          <div key={result.id} style={{ background: '#1e293b', borderRadius: '8px', padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <h3 style={{ margin: 0, color: '#38bdf8' }}>{result.title || 'Untitled'}</h3>
              <span style={{ color: '#64748b', fontSize: '0.75rem' }}>score: {result.score?.toFixed(2)}</span>
            </div>
            <p style={{ color: '#cbd5e1', margin: '0.5rem 0' }}>{result.snippet}</p>
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: '#64748b' }}>
              <span>Source: {result.source_id}</span>
              {result.published_at && <span>{new Date(result.published_at).toLocaleDateString()}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
