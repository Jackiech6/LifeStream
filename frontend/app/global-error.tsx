'use client';

/**
 * Catches root-level errors (including "Cannot find module" chunk errors in dev).
 * Must define its own <html> and <body> — it replaces the root layout.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const isChunkError =
    error?.message?.includes('Cannot find module') ||
    error?.message?.includes('Failed to fetch dynamically imported module');

  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif', background: '#f9fafb', padding: '2rem' }}>
        <div style={{ maxWidth: '28rem', margin: '0 auto', textAlign: 'center' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>
            Internal Server Error
          </h1>
          <p style={{ color: '#4b5563', marginBottom: '1.5rem' }}>
            {isChunkError
              ? 'The app hit a loading error (often caused by the dev server). Use production mode instead.'
              : error?.message || 'Something went wrong.'}
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => reset()}
              style={{
                padding: '0.5rem 1rem',
                background: '#0284c7',
                color: 'white',
                border: 'none',
                borderRadius: '0.5rem',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Try again
            </button>
            <a
              href="/"
              style={{
                padding: '0.5rem 1rem',
                border: '1px solid #d1d5db',
                color: '#374151',
                borderRadius: '0.5rem',
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              Go home
            </a>
          </div>
          <p style={{ marginTop: '1.5rem', fontSize: '0.875rem', color: '#6b7280' }}>
            Run in your terminal: <code style={{ background: '#e5e7eb', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>./scripts/start-frontend.sh</code> and open http://localhost:3000
          </p>
        </div>
      </body>
    </html>
  );
}
