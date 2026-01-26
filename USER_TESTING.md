# LifeStream – User Testing Guide

Use this guide to run through the app locally and verify upload → processing → summary.

---

## Prerequisites

- **Node.js** (v18+): for the frontend
- **Browser**: Chrome, Safari, or Firefox
- **`.env.local`**: Frontend must point at the staging API (see below)

---

## 1. Start the frontend

**Run the dev server in your own terminal** (from the project root):

```bash
./scripts/start-frontend.sh
```

Or manually:

```bash
cd frontend && npm run dev
```

Frontend runs at **http://localhost:3000**.  
If port 3000 is in use, Next.js will use 3001 (or the next free port).  
Ensure nothing else is bound to 3000 (e.g. another Next app or sandbox restriction).

---

## 2. Frontend environment

Ensure `frontend/.env.local` exists and contains:

```
NEXT_PUBLIC_API_URL=https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging
```

This makes the UI call the deployed staging API (presigned upload, confirm, status, summary, query).

---

## 3. User testing flow

### 3.1 Open the app

1. Go to **http://localhost:3000**
2. Use **Upload** in the nav, or open **http://localhost:3000/upload**

### 3.2 Upload a video

1. Choose a short video (e.g. MP4, &lt; 100 MB).  
   A ~1–2 minute clip is enough; longer videos take more time to process.
2. Drag & drop or click to select the file.
3. Wait for upload and confirmation.  
   You should be redirected to **`/jobs/{job_id}`**.

### 3.3 Watch status

1. On the job page, status should move: **queued** → **processing** → **completed**.
2. Processing usually takes **~5–6 minutes** for a 1–2 minute video (diarization, ASR, scene detection, etc.).
3. The page polls automatically; you can leave it open.

### 3.4 View summary

1. When status is **completed**, use **View summary** (or open **`/jobs/{job_id}/summary`**).
2. You should see the generated summary (markdown + time blocks).

### 3.5 Query (optional)

1. Go to **http://localhost:3000/chat**.
2. Enter a natural-language query about the uploaded video.
3. The app uses the staging **`/api/v1/query`** endpoint and Pinecone index.

---

## 4. Quick API smoke checks

Backend is deployed and ready. You can verify with:

```bash
# Health
curl -s "https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging/health"

# Presigned URL (returns upload_url, job_id, s3_key)
curl -s -X POST "https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging/api/v1/upload/presigned-url" \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.mp4"}'
```

---

## 5. Troubleshooting

| Issue | What to check |
|-------|----------------|
| **“Still queued” for a long time** | Job-ID mismatch fix is deployed. If it persists, try a **new** upload; use the latest frontend and avoid very old jobs. |
| **404 on status** | Confirm you’re using the **job ID** from the redirect after upload (same as in the URL). |
| **Frontend can’t reach API** | Ensure `NEXT_PUBLIC_API_URL` in `frontend/.env.local` matches the staging URL above. Restart `npm run dev` after changing `.env.local`. |
| **Upload fails** | Check browser console and network tab. Confirm presigned URL and confirm endpoints return 2xx. |
| **Processing errors** | Check ECS processor logs: **CloudWatch** → log group **`/ecs/lifestream-processor-staging`**. |

---

## 6. Deployed components

- **API**: Lambda (container) behind API Gateway (`/staging`)
- **Dispatcher**: Lambda consuming SQS, starting ECS tasks
- **Processor**: ECS Fargate tasks (Docker image from ECR)
- **Storage**: S3 (videos + results), DynamoDB (jobs + idempotency), Pinecone (index)

All of the above are deployed and ready for user testing.
