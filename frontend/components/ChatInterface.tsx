'use client';

import { useState } from 'react';
import { apiClient } from '@/lib/api';
import type { QueryRequest, SearchResult } from '@/lib/types';
import { format } from 'date-fns';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  results?: SearchResult[];
  timestamp: Date;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    date: '',
    video_id: '',
    speaker_ids: [] as string[],
    top_k: 5,
    min_score: 0.0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setQuery('');

    try {
      const request: QueryRequest = {
        query: query,
        top_k: filters.top_k,
        min_score: filters.min_score > 0 ? filters.min_score : undefined,
        date: filters.date || undefined,
        video_id: filters.video_id || undefined,
        speaker_ids: filters.speaker_ids.length > 0 ? filters.speaker_ids : undefined,
      };

      const response = await apiClient.queryMemory(request);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.answer || `Found ${response.total_results} relevant results`,
        results: response.results,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: error instanceof Error ? error.message : 'Failed to query memory',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col h-screen max-w-6xl mx-auto">
      <div className="p-4 sm:p-5 border-b bg-white/90 backdrop-blur-sm border-gray-200/80 shadow-sm">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-primary-700 to-primary-500 bg-clip-text text-transparent mb-4">Query Memory</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
            <input
              type="date"
              value={filters.date}
              onChange={(e) => setFilters({ ...filters, date: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Video ID</label>
            <input
              type="text"
              value={filters.video_id}
              onChange={(e) => setFilters({ ...filters, video_id: e.target.value })}
              placeholder="Optional"
              className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Top K Results</label>
            <input
              type="number"
              min="1"
              max="50"
              value={filters.top_k}
              onChange={(e) => setFilters({ ...filters, top_k: parseInt(e.target.value) || 5 })}
              className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Min Score</label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.1"
              value={filters.min_score}
              onChange={(e) => setFilters({ ...filters, min_score: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-12 max-w-md mx-auto">
            <p className="text-lg font-medium">Start a conversation with your memory</p>
            <p className="text-sm mt-2">Ask questions about your videos, meetings, or activities</p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-2xl p-4 shadow-sm ${
                message.type === 'user'
                  ? 'bg-gradient-to-r from-primary-600 to-primary-500 text-white'
                  : 'bg-white/90 backdrop-blur-sm border border-gray-200'
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              <p className={`text-xs mt-2 ${message.type === 'user' ? 'text-primary-100' : 'text-gray-500'}`}>
                {format(message.timestamp, 'HH:mm')}
              </p>

              {/* Search Results */}
              {message.results && message.results.length > 0 && (
                <div className="mt-4 space-y-3">
                  <p className="text-sm font-semibold mb-2">Search Results:</p>
                  {message.results.map((result) => (
                    <div
                      key={result.chunk_id}
                      className="p-3 bg-gray-50/80 rounded-xl border border-gray-200 hover:border-primary-300 transition-all"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="text-xs text-gray-500">
                          <span className="font-semibold">Score:</span> {result.score.toFixed(3)}
                        </div>
                        <div className="text-xs text-gray-500">
                          {formatTime(result.start_time)} - {formatTime(result.end_time)}
                        </div>
                      </div>
                      <p className="text-sm mb-2">{result.text}</p>
                      <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                        <span>📅 {result.date}</span>
                        {result.speakers.length > 0 && (
                          <span>👥 {result.speakers.join(', ')}</span>
                        )}
                        <span>🎥 {result.video_id}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white/90 border border-gray-200 rounded-2xl p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary-600 border-t-transparent" />
                <span className="text-sm text-gray-500">Searching...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 border-t bg-white/90 backdrop-blur-sm border-gray-200/80">
        <form onSubmit={handleSubmit} className="flex gap-2 max-w-4xl mx-auto">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about your videos..."
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="bg-gradient-to-r from-primary-600 to-primary-500 text-white px-6 py-2.5 rounded-xl font-semibold hover:from-primary-700 hover:to-primary-600 shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
