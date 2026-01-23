'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { format } from 'date-fns';
import Link from 'next/link';

interface JobStatusProps {
  jobId: string;
}

const STAGES = [
  { id: 'queued', label: 'Queued', icon: '⏳' },
  { id: 'processing', label: 'Processing', icon: '⚙️' },
  { id: 'completed', label: 'Completed', icon: '✅' },
  { id: 'failed', label: 'Failed', icon: '❌' },
];

export default function JobStatus({ jobId }: JobStatusProps) {
  const { getJob, updateJobStatus } = useAppStore();
  const [polling, setPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const job = getJob(jobId);

  useEffect(() => {
    if (!jobId) return;

    const fetchStatus = async () => {
      try {
        const status = await apiClient.getJobStatus(jobId);
        updateJobStatus(jobId, status);

        // Stop polling if completed or failed
        if (status.status === 'completed' || status.status === 'failed') {
          setPolling(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch status');
        setPolling(false);
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll every 2 seconds if still processing
    const interval = setInterval(() => {
      if (polling) {
        fetchStatus();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, polling, updateJobStatus]);

  if (!job) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Loading job status...</p>
      </div>
    );
  }

  const { status } = job;
  const currentStageIndex = STAGES.findIndex((s) => s.id === status.status);

  return (
    <div className="w-full max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Job Status</h2>
        <p className="text-sm text-gray-500">Job ID: {jobId}</p>
      </div>

      {/* Status Timeline */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          {STAGES.map((stage, index) => {
            const isActive = index <= currentStageIndex;
            const isCurrent = index === currentStageIndex;

            return (
              <div key={stage.id} className="flex-1 flex flex-col items-center">
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl mb-2 ${
                    isActive
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-200 text-gray-400'
                  } ${isCurrent ? 'ring-4 ring-primary-200' : ''}`}
                >
                  {stage.icon}
                </div>
                <span
                  className={`text-sm font-medium ${
                    isActive ? 'text-primary-600' : 'text-gray-400'
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>

        {/* Progress Bar */}
        {status.progress !== undefined && status.status === 'processing' && (
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-2">
              <span>Processing...</span>
              <span>{Math.round(status.progress * 100)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${status.progress * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Current Stage */}
        {status.current_stage && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-700">
              <span className="font-semibold">Current Stage:</span> {status.current_stage}
            </p>
          </div>
        )}
      </div>

      {/* Error Display */}
      {status.error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm font-semibold text-red-700 mb-1">Error:</p>
          <p className="text-sm text-red-600">{status.error}</p>
        </div>
      )}

      {/* Timestamps */}
      <div className="mb-6 space-y-2 text-sm text-gray-600">
        {status.created_at && (
          <p>
            <span className="font-semibold">Created:</span>{' '}
            {format(new Date(status.created_at), 'PPpp')}
          </p>
        )}
        {status.updated_at && (
          <p>
            <span className="font-semibold">Last Updated:</span>{' '}
            {format(new Date(status.updated_at), 'PPpp')}
          </p>
        )}
      </div>

      {/* Actions */}
      {status.status === 'completed' && (
        <div className="flex gap-4">
          <Link
            href={`/jobs/${jobId}/summary`}
            className="bg-primary-600 text-white py-2 px-6 rounded-lg font-semibold hover:bg-primary-700 transition-colors"
          >
            View Summary
          </Link>
          <Link
            href="/chat"
            className="bg-gray-200 text-gray-700 py-2 px-6 rounded-lg font-semibold hover:bg-gray-300 transition-colors"
          >
            Query Memory
          </Link>
        </div>
      )}

      {/* Polling Status */}
      {polling && status.status === 'processing' && (
        <div className="mt-4 text-sm text-gray-500">
          <span className="animate-pulse">●</span> Polling for updates...
        </div>
      )}

      {error && (
        <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700">
          {error}
        </div>
      )}
    </div>
  );
}
