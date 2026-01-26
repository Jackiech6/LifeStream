'use client';

import { useState } from 'react';
import Link from 'next/link';
import MemoryTab from '@/components/MemoryTab';

type HomeTab = 'overview' | 'memory';

export default function Home() {
  const [activeTab, setActiveTab] = useState<HomeTab>('overview');

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
      {/* Hero - extra padding so title descenders and gradient are not clipped */}
      <div className="text-center mb-10 pt-2 pb-4">
        <h1 className="text-4xl sm:text-5xl font-bold bg-gradient-to-r from-primary-700 to-primary-500 bg-clip-text text-transparent pb-1 leading-tight">
          LifeStream Intelligent Diary
        </h1>
        <p className="text-lg sm:text-xl text-gray-600 max-w-2xl mx-auto leading-relaxed mt-5">
          Transform your video footage into structured, searchable daily journals and meeting minutes
        </p>
      </div>

      {/* Tabs - full width bar with centered tab buttons */}
      <div className="w-full flex justify-center p-1 rounded-xl bg-gray-100/80 border border-gray-200/80 mb-10">
        <div className="flex gap-1 rounded-lg bg-transparent">
        <button
          type="button"
          onClick={() => setActiveTab('overview')}
          className={`flex-1 sm:flex-none px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'overview'
              ? 'bg-white text-primary-700 shadow-sm border border-gray-200'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/60'
          }`}
        >
          Overview
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('memory')}
          className={`flex-1 sm:flex-none px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'memory'
              ? 'bg-white text-primary-700 shadow-sm border border-gray-200'
              : 'text-gray-600 hover:text-gray-900 hover:bg-white/60'
          }`}
        >
          Memory
        </button>
        </div>
      </div>

      {activeTab === 'overview' && (
        <>
          {/* Two main actions: Upload + Query */}
          <div className="grid md:grid-cols-2 gap-8 mb-14">
            <Link
              href="/upload"
              className="group block bg-white/90 backdrop-blur-sm p-8 rounded-2xl shadow-lg border border-gray-100 hover:shadow-md hover:border-primary-200 transition-all duration-300"
            >
              <div className="w-14 h-14 rounded-xl bg-primary-100 text-primary-600 flex items-center justify-center text-2xl mb-5 group-hover:bg-primary-500 group-hover:text-white transition-colors">
                📹
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Upload Videos</h3>
              <p className="text-gray-600 mb-4 leading-relaxed">
                Upload your video files and let our AI process them into structured summaries. View status and open the summary when processing is complete.
              </p>
              <span className="inline-flex items-center text-primary-600 font-semibold group-hover:text-primary-700">
                Upload Video →
              </span>
            </Link>

            <Link
              href="/chat"
              className="group block bg-white/90 backdrop-blur-sm p-8 rounded-2xl shadow-lg border border-gray-100 hover:shadow-md hover:border-primary-200 transition-all duration-300"
            >
              <div className="w-14 h-14 rounded-xl bg-primary-100 text-primary-600 flex items-center justify-center text-2xl mb-5 group-hover:bg-primary-500 group-hover:text-white transition-colors">
                🔍
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Query Memory</h3>
              <p className="text-gray-600 mb-4 leading-relaxed">
                Search through your indexed videos using natural language queries
              </p>
              <span className="inline-flex items-center text-primary-600 font-semibold group-hover:text-primary-700">
                Start Querying →
              </span>
            </Link>
          </div>

          {/* How It Works */}
          <div className="bg-white/80 backdrop-blur-sm p-8 sm:p-10 rounded-2xl shadow-lg border border-gray-100">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">How It Works</h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {[
                { step: 1, title: 'Upload', desc: 'Upload your video file through our web interface' },
                { step: 2, title: 'Process', desc: 'AI extracts audio, transcribes speech, and analyzes video' },
                { step: 3, title: 'Summarize', desc: 'LLM generates structured summaries with time blocks and action items' },
                { step: 4, title: 'Search', desc: 'Query your indexed memories using semantic search' },
              ].map(({ step, title, desc }) => (
                <div key={step} className="flex flex-col">
                  <div className="text-2xl font-bold text-primary-600 mb-2">{step}</div>
                  <h4 className="font-semibold text-gray-900 mb-1">{title}</h4>
                  <p className="text-sm text-gray-600 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {activeTab === 'memory' && (
        <div>
          <p className="text-gray-600 mb-6">
            Processed videos and their indexed chunks in the vector database. You can delete chunks or entire videos (jobs); deleted data is removed from the vector store. Deleting a video automatically removes all its indexed chunks as well.
          </p>
          <MemoryTab />
        </div>
      )}
    </div>
  );
}
