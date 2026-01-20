# Stage 3 Implementation Plan – Cloud Deployment & Productization

**Document version:** 1.0  
**Author:** AI assistant (based on LifeStream spec)  
**Scope:** Detailed, implementation-ready plan for Stage 3 of LifeStream: Cloud Deployment & Productization, transforming local scripts into a scalable cloud service with web interface.

**Estimated Duration:** 1 Week  
**Primary Goal:** Deploy a working web service where users can upload videos and chat with their indexed data.

---

## 1. Goals & High-Level Design

### 1.1 Objectives

- **Objective:** Transform the local LifeStream pipeline into a cloud-deployed, scalable service with a web interface.
- **Inputs:**
  - Video file uploads via web interface
  - Natural language queries via chat interface
- **Outputs:**
  - RESTful API endpoints for video processing and querying
  - Web dashboard for video upload, status tracking, and chat interface
  - Event-driven processing pipeline triggered by uploads
  - Deployed service accessible via URL

### 1.2 Architecture Overview

```
┌─────────────────┐
│  Web Dashboard  │ (React/Next.js)
└────────┬────────┘
         │ HTTP/REST
┌────────▼─────────────────────────┐
│      API Gateway                  │ (FastAPI/Flask)
│  - upload_video                   │
│  - get_status                     │
│  - get_summary                    │
│  - query_memory                   │
└────────┬──────────────────────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    │         │              │              │
┌───▼───┐ ┌──▼───┐    ┌─────▼─────┐  ┌─────▼─────┐
│Object │ │Event │    │ Processing│  │  Vector   │
│Storage│ │Queue │    │  Workers  │  │   Store   │
│(S3)   │ │(SQS) │    │(Lambda/   │  │(Pinecone/ │
│       │ │      │    │ ECS)      │  │ Weaviate) │
└───────┘ └──────┘    └───────────┘  └───────────┘
```

### 1.3 Core Design Decisions

**Cloud Provider:** AWS (recommended for comprehensive services)
- **Alternative:** GCP (Cloud Functions, Cloud Storage) or Azure (Functions, Blob Storage)

**Compute Options:**
- **Serverless (Recommended):** AWS Lambda for processing (scales automatically, pay-per-use)
- **Alternative:** AWS ECS/Fargate (containers) for longer-running tasks

**Storage:**
- **Object Storage:** AWS S3 (for video files)
- **Vector Database:** Pinecone (managed, recommended) or Weaviate (self-hosted option)
- **Metadata Store:** PostgreSQL (AWS RDS) or MongoDB Atlas (document store)

**API Framework:**
- **Recommended:** FastAPI (async, auto-docs, type-safe)
- **Alternative:** Flask (simpler, more familiar)

**Frontend Framework:**
- **Recommended:** Next.js (React-based, SSR, easy deployment)
- **Alternative:** React + Vite (simpler setup)

---

## 2. Sub-Stage 3.1 – Cloud Infrastructure Setup

### 2.1.1. Cloud Provider Account Setup

**Goal:** Set up cloud provider account and configure IAM roles.

**Tasks:**
1. Create AWS account (or GCP/Azure)
2. Set up billing alerts
3. Create IAM user with programmatic access
4. Configure AWS CLI locally
5. Set up CloudFormation/Terraform for infrastructure-as-code

**Tools:**
- **AWS CLI:** `aws-cli` for infrastructure management
- **Terraform (Recommended):** Infrastructure-as-code (multi-cloud support)
- **Alternative:** AWS CloudFormation (AWS-native)

**Configuration Files:**
- `infrastructure/main.tf` - Terraform configuration
- `infrastructure/variables.tf` - Environment variables
- `.aws/credentials` - AWS credentials (local)

**Testing Strategy:**
- **Unit Test:** Validate Terraform/CloudFormation syntax
- **Integration Test:** Deploy to dev environment, verify resources created
- **Compliance Test:** Verify IAM roles follow least-privilege principle

### 2.1.2. Object Storage Setup

**Goal:** Configure cloud object storage for video uploads.

**Implementation:**
- Create S3 bucket (or GCS/Azure Blob equivalent)
- Configure CORS for web uploads
- Set up lifecycle policies (auto-delete after processing)
- Configure bucket notifications (trigger on upload)

**Tools:**
- **AWS S3:** Object storage
- **boto3:** Python SDK for S3 operations

**Key Functions:**
- `create_bucket()` - Initialize storage bucket
- `upload_file()` - Handle video uploads
- `generate_presigned_url()` - Direct client uploads
- `configure_notifications()` - Set up event triggers

**Testing Strategy:**
- **Unit Test:** Mock S3 operations, test upload/download logic
- **Integration Test:** Upload test video, verify file stored correctly
- **E2E Test:** Upload via web interface, verify S3 storage

### 2.1.3. Vector Database Migration

**Goal:** Migrate from local FAISS to managed vector database.

**Implementation:**
- Set up Pinecone account (or Weaviate self-hosted)
- Create index with appropriate dimensions (1536 for text-embedding-3-small)
- Migrate existing FAISS index (if any)
- Update `VectorStore` abstraction to use Pinecone client

**Tools:**
- **Pinecone (Recommended):** Managed vector database, free tier available
- **Alternative:** Weaviate (self-hosted on cloud VM)

**Key Functions:**
- `PineconeVectorStore.upsert()` - Replace FaissVectorStore
- `PineconeVectorStore.query()` - Query with filters
- `migrate_faiss_to_pinecone()` - One-time migration script

**Testing Strategy:**
- **Unit Test:** Mock Pinecone client, test upsert/query logic
- **Integration Test:** Index test chunks, verify retrieval
- **Migration Test:** Compare FAISS vs Pinecone results for same queries

---

## 3. Sub-Stage 3.2 – Event-Driven Processing Pipeline

### 3.1.1. Event Queue Setup

**Goal:** Set up message queue for asynchronous video processing.

**Implementation:**
- Create SQS queue (or GCP Pub/Sub, Azure Service Bus)
- Configure dead-letter queue for failed jobs
- Set up queue visibility timeout (based on processing time)

**Tools:**
- **AWS SQS:** Message queue service
- **boto3:** Python SDK for SQS

**Key Functions:**
- `send_processing_job()` - Enqueue video processing task
- `receive_job()` - Worker receives job from queue
- `update_job_status()` - Update processing status

**Testing Strategy:**
- **Unit Test:** Mock SQS, test message send/receive
- **Integration Test:** Send test message, verify worker receives it
- **E2E Test:** Upload video, verify job enqueued and processed

### 3.1.2. Processing Worker Implementation

**Goal:** Create stateless worker function that processes videos.

**Implementation:**
- Refactor `process_video()` to be fully stateless
- Accept S3 video path instead of local path
- Download video to `/tmp` (Lambda) or container storage
- Process using existing Stage 1 pipeline
- Upload results to S3
- Update job status in database
- Clean up temporary files

**Tools:**
- **AWS Lambda:** Serverless compute (recommended for cost efficiency)
- **Alternative:** AWS ECS/Fargate (for longer-running tasks)

**Key Functions:**
- `lambda_handler(event, context)` - Lambda entry point
- `process_video_from_s3(s3_path)` - Download and process
- `upload_results_to_s3(summary, s3_path)` - Save outputs

**Testing Strategy:**
- **Unit Test:** Mock S3 operations, test processing logic
- **Integration Test:** Deploy Lambda, trigger with test event
- **Load Test:** Process multiple videos concurrently
- **Error Test:** Test with corrupted videos, verify graceful failure

### 3.1.3. Trigger Configuration

**Goal:** Automatically trigger processing on video upload.

**Implementation:**
- Configure S3 bucket notification → SQS queue
- Or: S3 → Lambda directly (simpler, but less control)
- Set up error handling and retries

**Tools:**
- **AWS S3 Event Notifications:** Trigger on object creation
- **AWS Lambda:** Event handler

**Configuration:**
```json
{
  "Rules": [
    {
      "Name": "VideoUploadTrigger",
      "Status": "Enabled",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [{"Name": "suffix", "Value": ".mp4"}]
        }
      },
      "Target": {
        "Queue": "video-processing-queue"
      }
    }
  ]
}
```

**Testing Strategy:**
- **Integration Test:** Upload video to S3, verify trigger fires
- **E2E Test:** Upload via web, verify processing starts automatically

---

## 4. Sub-Stage 3.3 – REST API Gateway

### 4.1.1. API Framework Setup

**Goal:** Set up FastAPI application with proper structure.

**Implementation:**
- Create FastAPI application
- Set up CORS middleware
- Configure authentication (API keys or JWT)
- Set up request/response models (Pydantic)
- Add OpenAPI/Swagger documentation

**Tools:**
- **FastAPI:** Modern Python web framework
- **Uvicorn:** ASGI server
- **Pydantic:** Request/response validation

**Project Structure:**
```
src/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── routes/
│   │   ├── upload.py        # upload_video endpoint
│   │   ├── status.py        # get_status endpoint
│   │   ├── summary.py       # get_summary endpoint
│   │   └── query.py         # query_memory endpoint
│   ├── models/
│   │   ├── requests.py      # Request models
│   │   └── responses.py     # Response models
│   └── services/
│       ├── video_service.py  # Video processing logic
│       └── search_service.py # RAG query logic
```

**Testing Strategy:**
- **Unit Test:** Test each route handler with mocked services
- **Integration Test:** Test API with real database/S3
- **Schema Test:** Validate request/response models

### 4.1.2. Upload Endpoint

**Goal:** Implement `POST /api/v1/upload` endpoint.

**Implementation:**
- Accept multipart/form-data file upload
- Validate file type and size
- Generate unique job ID
- Upload to S3 with presigned URL or direct upload
- Enqueue processing job
- Return job ID and status

**Request Model:**
```python
class UploadRequest(BaseModel):
    file: UploadFile
    metadata: Optional[Dict[str, Any]] = None
```

**Response Model:**
```python
class UploadResponse(BaseModel):
    job_id: str
    status: str  # "queued"
    video_url: str
    estimated_completion: Optional[datetime] = None
```

**Testing Strategy:**
- **Unit Test:** Mock file upload, verify S3 upload and job enqueue
- **Integration Test:** Upload test video, verify stored in S3
- **Error Test:** Test invalid file types, oversized files

### 4.1.3. Status Endpoint

**Goal:** Implement `GET /api/v1/status/{job_id}` endpoint.

**Implementation:**
- Query job status from database (PostgreSQL/MongoDB)
- Return current processing stage
- Include progress percentage if available
- Return error message if failed

**Response Model:**
```python
class StatusResponse(BaseModel):
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    progress: Optional[float] = None  # 0.0 - 1.0
    current_stage: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

**Testing Strategy:**
- **Unit Test:** Mock database, test status retrieval
- **Integration Test:** Create job, verify status updates
- **E2E Test:** Upload video, poll status endpoint, verify updates

### 4.1.4. Summary Endpoint

**Goal:** Implement `GET /api/v1/summary/{job_id}` endpoint.

**Implementation:**
- Retrieve summary from S3 or database
- Return Markdown or JSON format
- Include video metadata

**Response Model:**
```python
class SummaryResponse(BaseModel):
    job_id: str
    date: str
    video_source: str
    summary_markdown: str
    time_blocks: List[TimeBlock]
    video_metadata: VideoMetadata
```

**Testing Strategy:**
- **Unit Test:** Mock S3/database, test summary retrieval
- **Integration Test:** Process video, retrieve summary
- **Format Test:** Verify Markdown format matches Stage 1 output

### 4.1.5. Query Endpoint

**Goal:** Implement `POST /api/v1/query` endpoint for RAG queries.

**Implementation:**
- Accept natural language query
- Embed query using OpenAI
- Query Pinecone vector store
- Return top-k relevant chunks
- Optionally: Use LLM to synthesize answer from chunks

**Request Model:**
```python
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: Optional[float] = None
    date: Optional[str] = None
    video_id: Optional[str] = None
    speaker_ids: Optional[List[str]] = None
```

**Response Model:**
```python
class QueryResponse(BaseModel):
    query: str
    results: List[SearchResult]
    answer: Optional[str] = None  # LLM-synthesized answer
```

**Testing Strategy:**
- **Unit Test:** Mock vector store, test query logic
- **Integration Test:** Query indexed summary, verify results
- **Accuracy Test:** Test with known queries, verify relevant chunks returned

### 4.1.6. API Deployment

**Goal:** Deploy API to cloud with proper scaling and monitoring.

**Implementation:**
- Deploy FastAPI to AWS ECS/Fargate or Lambda (API Gateway)
- Set up API Gateway (if using Lambda)
- Configure auto-scaling
- Set up CloudWatch logging
- Configure health check endpoint

**Tools:**
- **AWS ECS/Fargate:** Container deployment
- **AWS API Gateway:** If using Lambda
- **Docker:** Containerize FastAPI app

**Testing Strategy:**
- **Deployment Test:** Deploy to staging, verify endpoints accessible
- **Load Test:** Simulate concurrent requests, verify scaling
- **Monitoring Test:** Verify logs and metrics in CloudWatch

---

## 5. Sub-Stage 3.4 – Web Dashboard

### 5.1.1. Frontend Framework Setup

**Goal:** Set up Next.js application with proper structure.

**Implementation:**
- Initialize Next.js project
- Set up TypeScript
- Configure API client (axios/fetch)
- Set up state management (Zustand or React Context)
- Configure routing

**Tools:**
- **Next.js:** React framework with SSR
- **TypeScript:** Type safety
- **Tailwind CSS:** Styling (recommended for rapid development)
- **Axios:** HTTP client

**Project Structure:**
```
frontend/
├── app/                    # Next.js 13+ app directory
│   ├── page.tsx           # Home page
│   ├── upload/
│   │   └── page.tsx       # Upload page
│   ├── jobs/
│   │   └── [id]/
│   │       └── page.tsx   # Job status page
│   └── chat/
│       └── page.tsx       # Chat interface
├── components/
│   ├── VideoUpload.tsx
│   ├── JobStatus.tsx
│   ├── ChatInterface.tsx
│   └── SummaryViewer.tsx
├── lib/
│   ├── api.ts             # API client
│   └── types.ts           # TypeScript types
└── public/
```

**Testing Strategy:**
- **Unit Test:** Test React components with React Testing Library
- **Integration Test:** Test API integration
- **E2E Test:** Test full user flows with Playwright/Cypress

### 5.1.2. Video Upload Interface

**Goal:** Build UI for video file upload.

**Implementation:**
- Drag-and-drop file upload component
- Progress bar for upload
- File validation (type, size)
- Preview uploaded file metadata
- Display upload status

**Components:**
- `VideoUpload.tsx` - Main upload component
- `UploadProgress.tsx` - Progress indicator
- `FilePreview.tsx` - File metadata display

**Testing Strategy:**
- **Unit Test:** Test file validation logic
- **Integration Test:** Test upload to API
- **E2E Test:** Upload video via UI, verify processing starts

### 5.1.3. Job Status Dashboard

**Goal:** Build UI for tracking video processing status.

**Implementation:**
- Real-time status updates (polling or WebSocket)
- Progress indicator showing current stage
- Timeline view of processing stages
- Error display if processing fails
- Link to view summary when complete

**Components:**
- `JobStatus.tsx` - Status display
- `ProcessingTimeline.tsx` - Stage visualization
- `ErrorDisplay.tsx` - Error messages

**Testing Strategy:**
- **Unit Test:** Test status polling logic
- **Integration Test:** Test status updates from API
- **E2E Test:** Upload video, verify status updates in real-time

### 5.1.4. Summary Viewer

**Goal:** Build UI for displaying daily summaries.

**Implementation:**
- Markdown renderer for summary display
- Time block navigation
- Speaker highlighting
- Action items checklist
- Download summary as Markdown

**Components:**
- `SummaryViewer.tsx` - Main viewer
- `TimeBlockCard.tsx` - Individual time block
- `ActionItemsList.tsx` - Action items display
- `MarkdownRenderer.tsx` - Markdown → HTML

**Tools:**
- **react-markdown:** Markdown rendering
- **react-syntax-highlighter:** Code highlighting (if needed)

**Testing Strategy:**
- **Unit Test:** Test Markdown rendering
- **Integration Test:** Test summary display from API
- **E2E Test:** View summary after processing completes

### 5.1.5. Chat Interface

**Goal:** Build RAG-powered chat interface for querying indexed videos.

**Implementation:**
- Chat message interface
- Query input with filters (date, video, speaker)
- Display search results with timestamps
- Optionally: LLM-synthesized answers
- Link to source video/time

**Components:**
- `ChatInterface.tsx` - Main chat component
- `MessageList.tsx` - Chat history
- `QueryInput.tsx` - Query form with filters
- `SearchResults.tsx` - Display results
- `ResultCard.tsx` - Individual result card

**Features:**
- Real-time query results
- Filter by date range
- Filter by video
- Filter by speaker
- Click result to jump to video timestamp

**Testing Strategy:**
- **Unit Test:** Test query logic and result display
- **Integration Test:** Test query API integration
- **E2E Test:** Query indexed video, verify relevant results
- **Accuracy Test:** Test with known queries, verify correct chunks

### 5.1.6. Frontend Deployment

**Goal:** Deploy frontend to cloud hosting.

**Implementation:**
- Build Next.js production bundle
- Deploy to Vercel (recommended for Next.js) or AWS Amplify
- Configure environment variables
- Set up custom domain (optional)

**Tools:**
- **Vercel:** Next.js hosting (recommended)
- **Alternative:** AWS Amplify, Netlify

**Testing Strategy:**
- **Deployment Test:** Deploy to staging, verify all pages load
- **E2E Test:** Test full user journey on deployed site

---

## 6. Sub-Stage 3.5 – Database & State Management

### 6.1.1. Metadata Database Setup

**Goal:** Set up database for job status and metadata.

**Implementation:**
- Create PostgreSQL database (AWS RDS) or MongoDB Atlas
- Design schema for jobs, summaries, videos
- Set up connection pooling
- Create database migrations

**Schema (PostgreSQL):**
```sql
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY,
    video_s3_path TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    progress FLOAT DEFAULT 0.0,
    current_stage VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE summaries (
    job_id UUID PRIMARY KEY REFERENCES jobs(job_id),
    date DATE NOT NULL,
    summary_markdown TEXT NOT NULL,
    summary_json JSONB,
    video_metadata JSONB,
    indexed_at TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE videos (
    video_id UUID PRIMARY KEY,
    job_id UUID REFERENCES jobs(job_id),
    s3_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_size BIGINT,
    duration FLOAT,
    uploaded_at TIMESTAMP DEFAULT NOW()
);
```

**Tools:**
- **PostgreSQL:** Relational database (AWS RDS)
- **Alternative:** MongoDB Atlas (document store)
- **SQLAlchemy:** ORM for Python
- **Alembic:** Database migrations

**Testing Strategy:**
- **Unit Test:** Test database models and queries
- **Integration Test:** Test CRUD operations
- **Migration Test:** Test database migrations

### 6.1.2. Job Status Tracking

**Goal:** Implement job status tracking throughout pipeline.

**Implementation:**
- Update job status at each pipeline stage
- Store progress percentage
- Log errors with stack traces
- Set up status update API

**Key Functions:**
- `update_job_status(job_id, status, progress)` - Update status
- `get_job_status(job_id)` - Retrieve status
- `log_job_error(job_id, error)` - Log errors

**Testing Strategy:**
- **Unit Test:** Test status update logic
- **Integration Test:** Verify status updates during processing
- **E2E Test:** Monitor job status via API during processing

---

## 7. Testing Strategy Summary

### 7.1. Unit Tests

**Coverage:**
- All API route handlers (mocked dependencies)
- All service functions
- Database models and queries
- Frontend components
- Utility functions

**Tools:**
- **pytest:** Python testing
- **Jest + React Testing Library:** Frontend testing
- **unittest.mock:** Mocking dependencies

### 7.2. Integration Tests

**Coverage:**
- API endpoints with real database
- S3 upload/download operations
- SQS message send/receive
- Pinecone vector operations
- Full processing pipeline (test environment)

**Tools:**
- **pytest:** With real services (test environment)
- **LocalStack:** Local AWS services for testing
- **Testcontainers:** Docker containers for databases

### 7.3. End-to-End Tests

**Coverage:**
- Complete user journey: upload → process → query
- Web interface interactions
- API → Database → Storage flow
- Error handling and recovery

**Tools:**
- **Playwright:** E2E browser testing
- **Cypress:** Alternative E2E framework
- **Postman/Insomnia:** API E2E testing

### 7.4. Load & Performance Tests

**Coverage:**
- Concurrent video uploads
- Concurrent API requests
- Processing pipeline under load
- Database query performance

**Tools:**
- **Locust:** Load testing
- **Apache Bench (ab):** Simple load testing
- **AWS CloudWatch:** Performance monitoring

### 7.5. Security Tests

**Coverage:**
- API authentication/authorization
- File upload validation
- SQL injection prevention
- XSS prevention in frontend
- CORS configuration

**Tools:**
- **OWASP ZAP:** Security scanning
- **Bandit:** Python security linting
- **ESLint security plugins:** Frontend security

---

## 8. Deployment Checklist

### 8.1. Pre-Deployment

- [ ] All tests passing (unit, integration, E2E)
- [ ] Environment variables configured
- [ ] Cloud resources provisioned
- [ ] Database migrations run
- [ ] Vector database index created
- [ ] API documentation generated
- [ ] Frontend production build successful

### 8.2. Deployment Steps

1. **Infrastructure:**
   - Deploy cloud resources (Terraform/CloudFormation)
   - Verify all resources created
   - Configure IAM roles and permissions

2. **Backend:**
   - Deploy API to ECS/Lambda
   - Run database migrations
   - Configure environment variables
   - Test health check endpoint

3. **Frontend:**
   - Build production bundle
   - Deploy to Vercel/Amplify
   - Configure API endpoint
   - Test all pages load

4. **Integration:**
   - Test video upload → processing → query flow
   - Verify monitoring and logging
   - Test error scenarios

### 8.3. Post-Deployment

- [ ] Monitor CloudWatch logs
- [ ] Verify auto-scaling works
- [ ] Test error handling
- [ ] Check billing alerts
- [ ] Document deployment process

---

## 9. Required Accounts & Credentials

### 9.1. Cloud Provider Account

**AWS (Recommended):**
- **Account:** AWS account with billing enabled
- **IAM User:** Programmatic access user
- **Credentials:** Access Key ID + Secret Access Key
- **Region:** Choose region (e.g., `us-east-1`)
- **Cost:** Pay-as-you-go (free tier available for some services)

**Alternative Providers:**
- **GCP:** Google Cloud Platform account
- **Azure:** Microsoft Azure account

### 9.2. Vector Database

**Pinecone (Recommended):**
- **Account:** Pinecone account (free tier available)
- **API Key:** Pinecone API key
- **Index Name:** Create index with 1536 dimensions (text-embedding-3-small)

**Alternative:**
- **Weaviate:** Self-hosted on cloud VM (requires VM setup)

### 9.3. Database

**PostgreSQL (AWS RDS):**
- **Instance:** RDS PostgreSQL instance
- **Credentials:** Database username + password
- **Connection String:** RDS endpoint

**Alternative:**
- **MongoDB Atlas:** Free tier available
- **Connection String:** MongoDB connection string

### 9.4. Existing API Keys (from Stage 1 & 2)

**OpenAI:**
- **API Key:** Already configured (for LLM + embeddings)

**HuggingFace:**
- **Token:** Already configured (for diarization)

### 9.5. Frontend Hosting (Optional)

**Vercel:**
- **Account:** Vercel account (free tier available)
- **GitHub Integration:** Connect GitHub repo for auto-deployment

**Alternative:**
- **AWS Amplify:** Use AWS account
- **Netlify:** Free tier available

---

## 10. Environment Variables

### 10.1. Backend (.env)

```bash
# Cloud Provider
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=lifestream-videos
AWS_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...

# Database
DATABASE_URL=postgresql://user:password@rds-endpoint:5432/lifestream
# OR for MongoDB:
# MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/lifestream

# Vector Database
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=lifestream-index

# Existing (from Stage 1 & 2)
OPENAI_API_KEY=your_openai_key
HUGGINGFACE_TOKEN=your_hf_token

# API Configuration
API_KEY=your_api_key_for_auth  # Optional: API key authentication
CORS_ORIGINS=https://your-frontend-domain.com
```

### 10.2. Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_WS_URL=wss://api.your-domain.com  # If using WebSockets
```

---

## 11. Cost Estimation

### 11.1. AWS Services (Monthly Estimate)

**Development/Testing:**
- S3 Storage: ~$0.023/GB (first 50GB free)
- Lambda: 1M requests free, then $0.20 per 1M requests
- SQS: First 1M requests free
- RDS (t3.micro): ~$15/month (free tier: 750 hours/month)
- API Gateway: First 1M requests free
- **Estimated:** $20-50/month for development

**Production (100 videos/month, 1 hour each):**
- S3 Storage (100GB): ~$2.30
- Lambda (100 invocations): ~$0.01
- SQS: ~$0.40
- RDS (db.t3.small): ~$30
- API Gateway: ~$3.50
- **Estimated:** $40-60/month

### 11.2. Third-Party Services

**Pinecone:**
- Free tier: 1 index, 100K vectors
- Paid: ~$70/month for 1M vectors

**OpenAI:**
- GPT-4o: ~$0.01-0.03 per video (summarization)
- Embeddings: ~$0.0001 per video (text-embedding-3-small)

**Total Estimated Cost:** $100-150/month for moderate usage

---

## 12. Milestones & Timeline

### Week 1: Cloud Deployment

**Day 1-2: Infrastructure Setup (Sub-Stage 3.1)**
- Set up cloud account and IAM
- Configure S3 and database
- Set up Pinecone index
- **Deliverable:** Cloud resources provisioned

**Day 3-4: Event-Driven Pipeline (Sub-Stage 3.2)**
- Implement processing worker
- Set up SQS and triggers
- Test end-to-end processing
- **Deliverable:** Video upload triggers processing

**Day 5: REST API (Sub-Stage 3.3)**
- Implement all API endpoints
- Deploy API to cloud
- Test API endpoints
- **Deliverable:** Working REST API

**Day 6-7: Web Dashboard (Sub-Stage 3.4)**
- Build frontend components
- Integrate with API
- Deploy frontend
- **Deliverable:** Working web interface

---

## 13. Success Criteria

### 13.1. Functional Requirements

- ✅ Video upload via web interface works
- ✅ Processing automatically triggers on upload
- ✅ Status updates in real-time
- ✅ Summary accessible via API and web
- ✅ Chat interface queries indexed videos
- ✅ Results link to source video/timestamp

### 13.2. Performance Requirements

- ✅ One-hour video processed in < 20 minutes (as per spec)
- ✅ API response time < 500ms for queries
- ✅ Frontend loads in < 2 seconds
- ✅ Concurrent processing of multiple videos

### 13.3. Reliability Requirements

- ✅ 99% uptime for API
- ✅ Graceful error handling
- ✅ Automatic retries for failed jobs
- ✅ Dead-letter queue for failed processing

---

## 14. Next Steps After Stage 3

### 14.1. Enhancements

- **Advanced Features:**
  - User authentication and multi-tenancy
  - Video classification (meeting vs vlog) with detailed meeting summaries
  - Real-time processing progress via WebSockets
  - Video playback with transcript overlay
  - Export summaries to PDF/Word

- **Optimization:**
  - Caching for frequently accessed summaries
  - Batch processing for multiple videos
  - CDN for static assets
  - Database query optimization

- **Monitoring:**
  - Application Performance Monitoring (APM)
  - Cost tracking and alerts
  - Usage analytics dashboard

---

**Last Updated:** 2026-01-20  
**Status:** Ready for Implementation
