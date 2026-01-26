'use client';

import { useEffect, useState, useRef } from 'react';
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

// Pipeline sub-stages (order matches backend STAGE_ORDER for progress)
const PIPELINE_STAGES = [
  { id: 'started', label: 'Started' },
  { id: 'download', label: 'Downloading video' },
  { id: 'audio_extraction', label: 'Extracting audio' },
  { id: 'diarization', label: 'Speaker diarization' },
  { id: 'asr', label: 'Transcription (ASR)' },
  { id: 'scene_detection', label: 'Scene detection' },
  { id: 'keyframes', label: 'Keyframes' },
  { id: 'sync', label: 'Synchronizing' },
  { id: 'summarization', label: 'Summarizing' },
  { id: 'upload', label: 'Uploading results' },
  { id: 'indexing', label: 'Indexing memory' },
  { id: 'completed', label: 'Complete' },
];

const QUEUED_TOO_LONG_MS = 90_000; // 90s

function formatStageLabel(stageId: string): string {
  const found = PIPELINE_STAGES.find((s) => s.id === stageId);
  return found ? found.label : stageId.replace(/_/g, ' ');
}

export default function JobStatus({ jobId }: JobStatusProps) {
  const { getJob, updateJobStatus } = useAppStore();
  const [polling, setPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef<number>(Date.now());

  const job = getJob(jobId);

  useEffect(() => {
    if (!jobId) return;
    startedAt.current = Date.now();

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
      <div className="p-8 text-center bg-white/60 rounded-2xl border border-gray-100">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-primary-600 border-t-transparent mx-auto mb-3" />
        <p className="text-gray-500">Loading job status...</p>
      </div>
    );
  }

  const { status } = job;
  const currentStageIndex = STAGES.findIndex((s) => s.id === status.status);

  return (
    <div className="w-full max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-primary-700 to-primary-500 bg-clip-text text-transparent mb-2">Job Status</h2>
        <p className="text-sm text-gray-500 font-mono">Job ID: {jobId}</p>
      </div>

      {/* Status Timeline */}
      <div className="mb-8 bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-100 p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          {STAGES.map((stage, index) => {
            const isActive = index <= currentStageIndex;
            const isCurrent = index === currentStageIndex;

            return (
              <div key={stage.id} className="flex-1 flex flex-col items-center">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-2 transition-all ${
                    isActive ? 'bg-primary-600 text-white shadow-md' : 'bg-gray-200 text-gray-400'
                  } ${isCurrent ? 'ring-4 ring-primary-200 ring-offset-2' : ''}`}
                >
                  {stage.icon}
                </div>
                <span
                  className={`text-sm font-medium ${isActive ? 'text-primary-600' : 'text-gray-400'}`}
                >
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>

        {status.status === 'processing' && (
          <div className="mt-5 space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="font-medium text-gray-700">
                  {status.current_stage ? (
                    <>Current step: <span className="text-primary-700">{formatStageLabel(status.current_stage)}</span></>
                  ) : (
                    'Processing…'
                  )}
                </span>
                <span className="font-semibold text-primary-600 tabular-nums">
                  {status.progress != null ? `${Math.round(status.progress * 100)}%` : '—'}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-primary-600 to-primary-500 h-3 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${Math.min(100, (status.progress ?? 0) * 100)}%` }}
                />
              </div>
            </div>
            {/* Pipeline steps: show completed + current */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {PIPELINE_STAGES.map((stage) => {
                const isCurrent = status.current_stage === stage.id;
                const idx = PIPELINE_STAGES.findIndex((s) => s.id === stage.id);
                const currentIdx = status.current_stage
                  ? PIPELINE_STAGES.findIndex((s) => s.id === status.current_stage)
                  : -1;
                const isDone = currentIdx >= 0 && idx < currentIdx;
                return (
                  <div
                    key={stage.id}
                    className={`px-3 py-2 rounded-lg text-xs font-medium ${
                      isCurrent
                        ? 'bg-primary-100 text-primary-800 ring-1 ring-primary-300'
                        : isDone
                        ? 'bg-gray-100 text-gray-600'
                        : 'bg-gray-50 text-gray-400'
                    }`}
                  >
                    {isDone && <span className="mr-1.5">✓</span>}
                    {stage.label}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {status.error && (
        <div className="mb-6 p-4 bg-red-50/90 border border-red-200 rounded-xl">
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

      {status.status === 'completed' && (
        <div className="flex flex-wrap gap-3">
          <Link
            href={`/jobs/${jobId}/summary`}
            className="bg-gradient-to-r from-primary-600 to-primary-500 text-white py-2.5 px-6 rounded-xl font-semibold hover:from-primary-700 hover:to-primary-600 shadow-md hover:shadow-lg transition-all"
          >
            View Summary
          </Link>
          <Link
            href="/chat"
            className="bg-white border border-gray-200 text-gray-700 py-2.5 px-6 rounded-xl font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all"
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

      {status.status === 'queued' &&
        Date.now() - startedAt.current > QUEUED_TOO_LONG_MS && (
          <div className="mt-4 p-4 bg-amber-50/90 border border-amber-200 rounded-xl text-amber-800 text-sm">
            <p className="font-semibold mb-1">Still queued?</p>
            <p>
              Processing may have run under a different job. Try uploading again
              (we now prefer your job ID when S3 and confirm both trigger), or
              check the API <code className="bg-amber-100 px-1 rounded">/api/v1/status</code> for
              other recent jobs.
            </p>
          </div>
        )}

      {error && (
        <div className="mt-4 p-4 bg-amber-50/90 border border-amber-200 rounded-xl text-amber-800">
          {error}
        </div>
      )}
    </div>
  );
}
