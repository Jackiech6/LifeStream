# Frontend Deployment Guide

## Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Create `.env.local` file:

```bash
NEXT_PUBLIC_API_URL=https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging
```

Or get the URL from Terraform:

```bash
cd ../infrastructure
terraform output api_gateway_url
```

### 3. Run Development Server

```bash
npm run dev
```

Visit http://localhost:3000

## Production Build

```bash
npm run build
npm start
```

## Deployment Options

### Option 1: Vercel (Recommended for Next.js)

1. **Install Vercel CLI** (optional):
   ```bash
   npm i -g vercel
   ```

2. **Deploy**:
   ```bash
   vercel
   ```

3. **Configure Environment Variable**:
   - Go to Vercel Dashboard → Project Settings → Environment Variables
   - Add: `NEXT_PUBLIC_API_URL` = your API Gateway URL

4. **Auto-deploy from GitHub**:
   - Connect GitHub repository
   - Vercel will auto-deploy on push

### Option 2: AWS Amplify

1. **Connect Repository**:
   - Go to AWS Amplify Console
   - Connect your GitHub repository

2. **Configure Build Settings**:
   ```
   Build command: npm run build
   Output directory: .next
   ```

3. **Add Environment Variable**:
   - Add `NEXT_PUBLIC_API_URL` in Amplify Console

4. **Deploy**:
   - Amplify will build and deploy automatically

### Option 3: Docker

Create `Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
```

Build and run:

```bash
docker build -t lifestream-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=your-url lifestream-frontend
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_API_URL` | API Gateway URL | Yes |

## Troubleshooting

### CORS Issues

If you see CORS errors, ensure the API Gateway has CORS configured correctly. The backend API should allow requests from your frontend domain.

### API Connection Issues

1. Verify `NEXT_PUBLIC_API_URL` is set correctly
2. Check API Gateway is accessible
3. Test API health endpoint: `curl $NEXT_PUBLIC_API_URL/health`

### Build Errors

1. Clear `.next` directory: `rm -rf .next`
2. Reinstall dependencies: `rm -rf node_modules && npm install`
3. Check Node.js version: `node --version` (should be 18+)

## Production Checklist

- [ ] Environment variables configured
- [ ] API Gateway URL is correct
- [ ] CORS configured on backend
- [ ] Build succeeds locally
- [ ] All pages load correctly
- [ ] Upload flow works end-to-end
- [ ] Status polling works
- [ ] Summary viewer displays correctly
- [ ] Chat interface queries work
