'use client';

import { useEffect, useState, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import type { MemoryJobItem, MemoryChunkItem } from '@/lib/types';
import { format } from 'date-fns';

type TabData = {
  jobs: MemoryJobItem[];
  chunks: MemoryChunkItem[];
};

export default function MemoryTab() {
  const [data, setData] = useState<TabData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobIds, setSelectedJobIds] = useState<Set<string>>(new Set());
  const [selectedChunkIds, setSelectedChunkIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const fetchMemory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getMemory();
      setData({ jobs: res.jobs, chunks: res.chunks });
      setSelectedJobIds(new Set());
      setSelectedChunkIds(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memory');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMemory();
  }, [fetchMemory]);

  const toggleJob = (jobId: string) => {
    setSelectedJobIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  const toggleChunk = (chunkId: string) => {
    setSelectedChunkIds((prev) => {
      const next = new Set(prev);
      if (next.has(chunkId)) next.delete(chunkId);
      else next.add(chunkId);
      return next;
    });
  };

  const selectAllJobs = () => {
    if (!data?.jobs.length) return;
    const allSelected = selectedJobIds.size === data.jobs.length;
    setSelectedJobIds(allSelected ? new Set() : new Set(data.jobs.map((j) => j.job_id)));
  };

  const selectAllChunks = () => {
    if (!data?.chunks.length) return;
    const allSelected = selectedChunkIds.size === data.chunks.length;
    setSelectedChunkIds(allSelected ? new Set() : new Set(data.chunks.map((c) => c.id)));
  };

  const handleDeleteChunks = async () => {
    if (selectedChunkIds.size === 0) return;
    setDeleting(true);
    setError(null);
    try {
      await apiClient.deleteChunks(Array.from(selectedChunkIds));
      await fetchMemory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete chunks');
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteJobs = async () => {
    if (selectedJobIds.size === 0) return;
    setDeleting(true);
    setError(null);
    try {
      await apiClient.deleteJobs(Array.from(selectedJobIds));
      await fetchMemory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete videos');
    } finally {
      setDeleting(false);
    }
  };

  const displayS3Key = (key: string) => {
    if (!key) return '—';
    const parts = key.split('/');
    return parts[parts.length - 1] || key;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="rounded-2xl bg-white/80 backdrop-blur-sm p-8 shadow-lg border border-gray-100">
          <div className="animate-pulse flex flex-col items-center gap-3">
            <div className="h-8 w-8 rounded-full border-2 border-primary-500 border-t-transparent animate-spin" />
            <p className="text-gray-600">Loading memory…</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-red-50/90 border border-red-200 p-6 text-red-800">
        <p className="font-medium mb-2">Error loading memory</p>
        <p className="text-sm mb-4">{error}</p>
        <button
          type="button"
          onClick={fetchMemory}
          className="px-4 py-2 rounded-xl bg-red-100 hover:bg-red-200 text-red-800 font-medium text-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { jobs, chunks } = data;
  const hasJobs = jobs.length > 0;
  const hasChunks = chunks.length > 0;
  const allJobsSelected = hasJobs && selectedJobIds.size === jobs.length;
  const allChunksSelected = hasChunks && selectedChunkIds.size === chunks.length;

  return (
    <div className="space-y-8">
      {error && (
        <div className="rounded-xl bg-red-50/90 border border-red-200 p-4 text-red-800 text-sm">
          {error}
        </div>
      )}

      {/* Processed Videos */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Processed Videos</h2>
            <p className="text-xs text-gray-500 mt-0.5">Deleting a video also removes all its chunks from the vector store.</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {hasJobs && (
              <>
                <button
                  type="button"
                  onClick={selectAllJobs}
                  className="text-sm font-medium text-primary-600 hover:text-primary-700 px-3 py-1.5 rounded-lg hover:bg-primary-50"
                >
                  {allJobsSelected ? 'Deselect all' : 'Select all'}
                </button>
                <button
                  type="button"
                  onClick={handleDeleteJobs}
                  disabled={selectedJobIds.size === 0 || deleting}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deleting ? 'Deleting…' : `Delete selected (${selectedJobIds.size})`}
                </button>
              </>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          {!hasJobs ? (
            <p className="px-6 py-8 text-gray-500 text-center">No processed videos yet. Upload and complete a job to see it here.</p>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-100">
                  <th className="w-10 px-4 py-3 text-gray-600 font-medium text-sm">Select</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Job ID</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">File</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Created</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Chunks</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id} className="border-b border-gray-100 hover:bg-gray-50/50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedJobIds.has(job.job_id)}
                        onChange={() => toggleJob(job.job_id)}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                    </td>
                    <td className="px-4 py-3 font-mono text-sm text-gray-800">{job.job_id.slice(0, 8)}…</td>
                    <td className="px-4 py-3 text-sm text-gray-700" title={job.s3_key}>
                      {displayS3Key(job.s3_key)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {job.created_at ? format(new Date(job.created_at), 'MMM d, yyyy HH:mm') : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{job.chunk_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Chunks */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-lg font-bold text-gray-900">Indexed Chunks</h2>
          <div className="flex items-center gap-2 flex-wrap">
            {hasChunks && (
              <>
                <button
                  type="button"
                  onClick={selectAllChunks}
                  className="text-sm font-medium text-primary-600 hover:text-primary-700 px-3 py-1.5 rounded-lg hover:bg-primary-50"
                >
                  {allChunksSelected ? 'Deselect all' : 'Select all'}
                </button>
                <button
                  type="button"
                  onClick={handleDeleteChunks}
                  disabled={selectedChunkIds.size === 0 || deleting}
                  className="px-4 py-2 rounded-xl text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deleting ? 'Deleting…' : `Delete selected (${selectedChunkIds.size})`}
                </button>
              </>
            )}
          </div>
        </div>
        <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
          {!hasChunks ? (
            <p className="px-6 py-8 text-gray-500 text-center">No chunks in the vector store yet.</p>
          ) : (
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-gray-50/95 z-10">
                <tr className="border-b border-gray-100">
                  <th className="w-10 px-4 py-3 text-gray-600 font-medium text-sm">Select</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Chunk ID</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Video</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Date</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Type</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm">Time</th>
                  <th className="px-4 py-3 text-gray-600 font-medium text-sm max-w-[200px]">Text preview</th>
                </tr>
              </thead>
              <tbody>
                {chunks.map((chunk) => (
                  <tr key={chunk.id} className="border-b border-gray-100 hover:bg-gray-50/50">
                    <td className="px-4 py-2">
                      <input
                        type="checkbox"
                        checked={selectedChunkIds.has(chunk.id)}
                        onChange={() => toggleChunk(chunk.id)}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-600" title={chunk.id}>
                      {chunk.id.slice(0, 12)}…
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 max-w-[120px] truncate" title={chunk.video_id}>
                      {chunk.video_id ? chunk.video_id.split('/').pop() || chunk.video_id : '—'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-700">{chunk.date ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-700">{chunk.source_type ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {chunk.start_time != null && chunk.end_time != null
                        ? `${chunk.start_time.toFixed(0)}s–${chunk.end_time.toFixed(0)}s`
                        : '—'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-700 max-w-[200px] truncate" title={chunk.text ?? ''}>
                      {chunk.text ? (chunk.text.length > 60 ? chunk.text.slice(0, 57) + '…' : chunk.text) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
