'use client';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Something went wrong</h1>
        <p className="text-gray-600 mb-6">
          {error?.message || 'An unexpected error occurred.'}
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={reset}
            className="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700"
          >
            Try again
          </button>
          <a
            href="/"
            className="px-4 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
          >
            Go home
          </a>
        </div>
        <p className="mt-6 text-sm text-gray-500">
          If this persists, run <code className="bg-gray-200 px-1 rounded">./scripts/start-frontend.sh</code> and avoid <code className="bg-gray-200 px-1 rounded">npm run dev</code>.
        </p>
      </div>
    </div>
  );
}
