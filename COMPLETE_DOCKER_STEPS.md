# Complete Docker & Deployment Steps

## Step 1: Start Docker Desktop (Manual)

1. **Open Docker Desktop:**
   - Press `Cmd + Space` (Spotlight)
   - Type `Docker` and press Enter
   - OR: Applications → Docker → Docker Desktop

2. **Wait for startup:**
   - Docker icon appears in menu bar
   - Wait for "Docker Desktop is running" status
   - First launch: 1-2 minutes

3. **Verify Docker is ready:**
   ```bash
   docker ps
   ```
   **Expected Output (SUCCESS):**
   ```
   CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
   ```
   (Empty list is OK - just means no containers are running)

   ```bash
   docker info | head -10
   ```
   **Expected Output (SUCCESS):**
   ```
   Client:
    Version:    28.0.4
    Context:    desktop-linux
   Server:
    Containers: 0
     Running: 0
   ...
   ```

   **Success Indicators:**
   - ✅ `docker ps` returns without "Cannot connect" error
   - ✅ `docker info` shows Server information
   - ✅ No connection errors

   **If errors occur:**
   - Wait 30 seconds and retry
   - Restart Docker Desktop if needed

## Step 2: Build and Push Container Image

**After Docker is running, execute:**

```bash
cd /Users/chenjackie/Desktop/LifeStream
./scripts/build_and_push_processor_image.sh
```

**Expected Output:**
```
✅ Image pushed successfully!
   Image URI: 533267430850.dkr.ecr.us-east-1.amazonaws.com/lifestream-lambda-processor-staging:latest
```

**Then verify image exists:**
```bash
aws ecr describe-images --repository-name lifestream-lambda-processor-staging --region us-east-1
```

**Expected Output:** Should show image details with tags and size

## Step 3: Complete Terraform Deployment

```bash
cd /Users/chenjackie/Desktop/LifeStream/infrastructure
terraform apply -auto-approve
```

**Expected Results:**
- Lambda function created
- Event source mapping created
- All resources deployed

## Step 4: Verify Lambda Function

```bash
aws lambda get-function --function-name lifestream-video-processor-staging \
  --query 'Configuration.[FunctionName,State,PackageType,Code.ImageUri]' \
  --output table \
  --region us-east-1
```

**Expected Output:**
```
------------------------------------------------------------
|          GetFunction Configuration Results               |
+-----------------+----------+--------------+-------------+
|  FunctionName   |  State   | PackageType  |  ImageUri   |
+-----------------+----------+--------------+-------------+
|  lifestream-... |  Active  |    Image     |  ECR URI    |
+-----------------+----------+--------------+-------------+
```

**Verify Event Source Mapping:**
```bash
aws lambda list-event-source-mappings \
  --function-name lifestream-video-processor-staging \
  --query 'EventSourceMappings[0].[UUID,State,EventSourceArn]' \
  --output table \
  --region us-east-1
```

**Expected Output:**
```
----------------------------------------
|     ListEventSourceMappings          |
+----------+--------+------------------+
|   UUID   | State  | EventSourceArn   |
+----------+--------+------------------+
|  abc123  |Enabled |  SQS ARN         |
+----------+--------+------------------+
```

## Step 5: Run Trigger Test

```bash
# Get queue URL
QUEUE_URL=$(cd /Users/chenjackie/Desktop/LifeStream/infrastructure && terraform output -raw sqs_queue_url)

# Send test message
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"job_id":"test-123","video_s3_key":"uploads/test.mp4","video_s3_bucket":"lifestream-videos-staging-533267430850"}' \
  --region us-east-1

# Check Lambda logs
aws logs tail /aws/lambda/lifestream-video-processor-staging \
  --since 10m \
  --format short \
  --region us-east-1

# Check queue status
aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --region us-east-1
```

**Expected Results:**
- Message sent successfully (returns MessageId)
- Lambda logs show invocation and processing
- Queue shows messages processed (ApproximateNumberOfMessages = 0 after processing)
