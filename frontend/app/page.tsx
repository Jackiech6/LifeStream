import Link from 'next/link';

export default function Home() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          LifeStream Intelligent Diary
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          Transform your video footage into structured, searchable daily journals and meeting minutes
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-6 mb-12">
        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div className="text-4xl mb-4">📹</div>
          <h3 className="text-xl font-semibold mb-2">Upload Videos</h3>
          <p className="text-gray-600 mb-4">
            Upload your video files and let our AI process them into structured summaries
          </p>
          <Link
            href="/upload"
            className="text-primary-600 font-semibold hover:text-primary-700"
          >
            Upload Video →
          </Link>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div className="text-4xl mb-4">📊</div>
          <h3 className="text-xl font-semibold mb-2">View Summaries</h3>
          <p className="text-gray-600 mb-4">
            Access detailed summaries with time blocks, transcripts, and action items
          </p>
          <Link
            href="/upload"
            className="text-primary-600 font-semibold hover:text-primary-700"
          >
            Get Started →
          </Link>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <div className="text-4xl mb-4">🔍</div>
          <h3 className="text-xl font-semibold mb-2">Query Memory</h3>
          <p className="text-gray-600 mb-4">
            Search through your indexed videos using natural language queries
          </p>
          <Link
            href="/chat"
            className="text-primary-600 font-semibold hover:text-primary-700"
          >
            Start Querying →
          </Link>
        </div>
      </div>

      <div className="bg-white p-8 rounded-lg shadow-md border border-gray-200">
        <h2 className="text-2xl font-bold mb-4">How It Works</h2>
        <div className="grid md:grid-cols-4 gap-6">
          <div>
            <div className="text-3xl font-bold text-primary-600 mb-2">1</div>
            <h4 className="font-semibold mb-2">Upload</h4>
            <p className="text-sm text-gray-600">
              Upload your video file through our web interface
            </p>
          </div>
          <div>
            <div className="text-3xl font-bold text-primary-600 mb-2">2</div>
            <h4 className="font-semibold mb-2">Process</h4>
            <p className="text-sm text-gray-600">
              AI extracts audio, transcribes speech, and analyzes video
            </p>
          </div>
          <div>
            <div className="text-3xl font-bold text-primary-600 mb-2">3</div>
            <h4 className="font-semibold mb-2">Summarize</h4>
            <p className="text-sm text-gray-600">
              LLM generates structured summaries with time blocks and action items
            </p>
          </div>
          <div>
            <div className="text-3xl font-bold text-primary-600 mb-2">4</div>
            <h4 className="font-semibold mb-2">Search</h4>
            <p className="text-sm text-gray-600">
              Query your indexed memories using semantic search
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
