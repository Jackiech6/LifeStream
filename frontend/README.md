# LifeStream Frontend

Next.js web dashboard for the LifeStream Intelligent Diary application.

## Features

- 📹 **Video Upload**: Drag-and-drop interface with progress tracking
- 📊 **Job Status**: Real-time status updates with timeline visualization
- 📝 **Summary Viewer**: Markdown rendering with time blocks and action items
- 🔍 **Chat Interface**: RAG-powered semantic search with filters

## Setup

### Prerequisites

- Node.js 18+ and npm/yarn
- API Gateway URL (configured via environment variable)

### Installation

```bash
cd frontend
npm install
```

### Environment Variables

Create a `.env.local` file:

```bash
NEXT_PUBLIC_API_URL=https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/staging
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
npm run build
npm start
```

## Deployment

### Vercel (Recommended)

1. Push code to GitHub
2. Import project in Vercel
3. Configure environment variable `NEXT_PUBLIC_API_URL`
4. Deploy

### AWS Amplify

1. Connect GitHub repository
2. Configure build settings:
   - Build command: `npm run build`
   - Output directory: `.next`
3. Add environment variable `NEXT_PUBLIC_API_URL`
4. Deploy

## Project Structure

```
frontend/
├── app/                    # Next.js 13+ app directory
│   ├── layout.tsx         # Root layout with navigation
│   ├── page.tsx           # Home page
│   ├── upload/            # Upload page
│   ├── jobs/[id]/         # Job status page
│   └── chat/              # Chat interface page
├── components/            # React components
│   ├── VideoUpload.tsx
│   ├── JobStatus.tsx
│   ├── SummaryViewer.tsx
│   ├── ChatInterface.tsx
│   └── Navigation.tsx
├── lib/                   # Utilities
│   ├── api.ts            # API client
│   ├── types.ts          # TypeScript types
│   └── store.ts          # Zustand state management
└── public/               # Static assets
```

## API Integration

The frontend connects to the LifeStream backend API via the configured `NEXT_PUBLIC_API_URL`. All API calls are handled through the `apiClient` in `lib/api.ts`.

## Technologies

- **Next.js 14**: React framework with App Router
- **TypeScript**: Type safety
- **Tailwind CSS**: Styling
- **Zustand**: State management
- **Axios**: HTTP client
- **React Markdown**: Markdown rendering
- **date-fns**: Date formatting
