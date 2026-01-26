'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { apiClient } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { format } from 'date-fns';
import type { SummaryResponse } from '@/lib/types';

interface SummaryViewerProps {
  jobId: string;
}

export default function SummaryViewer({ jobId }: SummaryViewerProps) {
  const { getJob, setJobSummary } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        setLoading(true);
        const job = getJob(jobId);
        
        // Use cached summary if available
        if (job?.summary) {
          setSummary(job.summary);
          setLoading(false);
          return;
        }

        // Fetch from API
        const data = await apiClient.getSummary(jobId);
        if (typeof data === 'string') {
          // Markdown format - convert to SummaryResponse-like structure
          setSummary({
            job_id: jobId,
            date: new Date().toISOString().split('T')[0],
            video_source: 'Unknown',
            summary_markdown: data,
            time_blocks: [],
          });
        } else {
          setSummary(data);
          setJobSummary(jobId, data);
        }
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load summary');
        setLoading(false);
      }
    };

    if (jobId) {
      fetchSummary();
    }
  }, [jobId, getJob, setJobSummary]);

  const handleDownload = () => {
    if (!summary) return;

    const blob = new Blob([summary.summary_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `summary-${jobId}-${summary.date}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="p-8 text-center bg-white/60 rounded-2xl border border-gray-100 backdrop-blur-sm">
        <div className="animate-spin rounded-full h-12 w-12 border-2 border-primary-600 border-t-transparent mx-auto" />
        <p className="mt-4 text-gray-500">Loading summary...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50/90 border border-red-200 rounded-xl p-4">
          <p className="text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No summary available</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto p-6">
      <div className="mb-6 flex flex-wrap justify-between items-start gap-4 bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-100 p-6 shadow-lg">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-primary-700 to-primary-500 bg-clip-text text-transparent mb-2">Daily Summary</h2>
          <div className="text-sm text-gray-500 space-y-1">
            <p>Date: {format(new Date(summary.date), 'PP')}</p>
            <p>Source: {summary.video_source}</p>
            {summary.video_metadata && (
              <p>
                Duration: {summary.video_metadata.duration
                  ? `${Math.round(summary.video_metadata.duration / 60)} minutes`
                  : 'Unknown'}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={handleDownload}
          className="bg-gradient-to-r from-primary-600 to-primary-500 text-white py-2.5 px-5 rounded-xl font-semibold hover:from-primary-700 hover:to-primary-600 shadow-md hover:shadow-lg transition-all"
        >
          Download Markdown
        </button>
      </div>

      {summary.time_blocks && summary.time_blocks.length > 0 && (
        <div className="mb-6 p-5 bg-white/70 backdrop-blur-sm rounded-2xl border border-gray-100 shadow">
          <h3 className="font-semibold text-gray-900 mb-3">Time Blocks</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {summary.time_blocks.map((block, index) => (
              <div
                key={index}
                className="p-3 bg-white rounded-xl border border-gray-200 hover:border-primary-300 hover:shadow-sm transition-all"
              >
                <div className="text-sm font-semibold text-primary-600">
                  {block.start_time} - {block.end_time}
                </div>
                {block.activity && (
                  <div className="text-sm text-gray-600 mt-1">{block.activity}</div>
                )}
                {block.location && (
                  <div className="text-xs text-gray-500 mt-1">📍 {block.location}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {summary.time_blocks.some((block) => block.action_items && block.action_items.length > 0) && (
        <div className="mb-6 p-5 bg-primary-50/70 rounded-2xl border border-primary-100">
          <h3 className="font-semibold text-gray-900 mb-3">Action Items</h3>
          <ul className="space-y-2">
            {summary.time_blocks.flatMap((block, blockIndex) =>
              (block.action_items || []).map((item, itemIndex) => (
                <li key={`${blockIndex}-${itemIndex}`} className="flex items-start">
                  <span className="mr-2">☐</span>
                  <span className="text-sm">{item}</span>
                </li>
              ))
            )}
          </ul>
        </div>
      )}

      <div className="prose prose-lg max-w-none bg-white/80 backdrop-blur-sm p-6 sm:p-8 rounded-2xl border border-gray-100 shadow-lg">
        <ReactMarkdown>{summary.summary_markdown}</ReactMarkdown>
      </div>
    </div>
  );
}
