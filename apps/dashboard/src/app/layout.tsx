export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif', background: '#0f172a', color: '#e2e8f0' }}>
        <nav style={{ padding: '1rem 2rem', borderBottom: '1px solid #334155', display: 'flex', gap: '2rem', alignItems: 'center' }}>
          <strong style={{ fontSize: '1.2rem', color: '#38bdf8' }}>Market Intelligence</strong>
          <a href="/" style={{ color: '#94a3b8', textDecoration: 'none' }}>Dashboard</a>
          <a href="/search" style={{ color: '#94a3b8', textDecoration: 'none' }}>Search</a>
          <a href="/signals" style={{ color: '#94a3b8', textDecoration: 'none' }}>Signals</a>
          <a href="/narratives" style={{ color: '#94a3b8', textDecoration: 'none' }}>Narratives</a>
        </nav>
        <main style={{ padding: '2rem' }}>{children}</main>
      </body>
    </html>
  );
}
