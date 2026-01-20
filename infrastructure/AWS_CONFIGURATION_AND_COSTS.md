# AWS Infrastructure Configuration & Cost Analysis

**Project:** LifeStream Intelligent Diary  
**Environment:** Development  
**Region:** us-east-1 (N. Virginia)  
**Date:** 2026-01-20

---

## Executive Summary

This document details all AWS infrastructure configurations for LifeStream Stage 3, provides justifications for each architectural decision, and includes accurate cost estimates based on current AWS pricing (2024-2025).

**Total Estimated Monthly Cost:** $25-45 USD (development environment)  
**Total Estimated Monthly Cost:** $60-120 USD (production environment with moderate usage)

---

## Table of Contents

1. [Storage: Amazon S3](#1-storage-amazon-s3)
2. [Message Queue: Amazon SQS](#2-message-queue-amazon-sqs)
3. [Database: Amazon RDS PostgreSQL](#3-database-amazon-rds-postgresql)
4. [Compute: AWS Lambda (Future)](#4-compute-aws-lambda-future)
5. [Security: IAM Roles & Policies](#5-security-iam-roles--policies)
6. [Networking: VPC, Subnets, Security Groups](#6-networking-vpc-subnets-security-groups)
7. [Monitoring: CloudWatch & Billing Alerts](#7-monitoring-cloudwatch--billing-alerts)
8. [Cost Breakdown Summary](#8-cost-breakdown-summary)
9. [Cost Optimization Recommendations](#9-cost-optimization-recommendations)

---

## 1. Storage: Amazon S3

### Configuration

**Resource:** `aws_s3_bucket.videos`  
**Bucket Name:** `lifestream-videos-dev-533267430850` (auto-generated)  
**Storage Class:** Standard  
**Region:** us-east-1

**Features Configured:**
- ✅ **Versioning:** Enabled (for data protection)
- ✅ **Lifecycle Policy:** Auto-delete after 30 days
- ✅ **CORS:** Enabled for web uploads
- ✅ **Public Access:** Blocked (security)
- ✅ **Encryption:** Server-side encryption (default)

### Why S3 is the Best Choice

1. **Scalability:** S3 automatically scales from bytes to petabytes without capacity planning
2. **Durability:** 99.999999999% (11 9's) durability - virtually no data loss risk
3. **Cost-Effective:** Pay only for what you store, no upfront costs
4. **Integration:** Native integration with Lambda, SQS, and other AWS services
5. **Performance:** Designed for high-throughput uploads/downloads
6. **Lifecycle Management:** Built-in policies to automatically manage object lifecycle

**Alternatives Considered:**
- **EBS Volumes:** Not suitable for object storage, limited scalability
- **EFS:** More expensive, overkill for video files
- **Glacier:** Cheaper but retrieval delays make it unsuitable for active processing

### Cost Breakdown

**Assumptions:**
- Average video size: 500 MB (1 hour video, compressed)
- Videos processed per month: 20 videos
- Average storage: 10 GB (videos stored for 30 days before deletion)
- Data transfer: 5 GB/month (uploads/downloads)

**Monthly Costs:**

| Component | Usage | Unit Price | Monthly Cost |
|-----------|-------|------------|--------------|
| **Storage (Standard)** | 10 GB | $0.023/GB | **$0.23** |
| **PUT Requests** | 20 videos | $0.005 per 1,000 | **$0.00** |
| **GET Requests** | 100 requests | $0.0004 per 1,000 | **$0.00** |
| **Data Transfer Out** | 5 GB | First 100 GB free | **$0.00** |
| **Lifecycle Transitions** | N/A | Free | **$0.00** |

**Total S3 Monthly Cost: ~$0.25 USD**

**Annual Cost: ~$3.00 USD**

### Cost Optimization Notes

- **Lifecycle Policy:** Automatically deletes videos after 30 days, preventing storage bloat
- **Versioning:** Can be disabled if not needed (saves ~$0.10/month for version storage)
- **Storage Class:** Using Standard class for active access; could use Intelligent-Tiering for automatic optimization

---

## 2. Message Queue: Amazon SQS

### Configuration

**Resource:** `aws_sqs_queue.video_processing`  
**Queue Name:** `lifestream-video-processing-dev`  
**Type:** Standard Queue

**Features Configured:**
- ✅ **Visibility Timeout:** 960 seconds (16 minutes) - matches Lambda timeout + buffer
- ✅ **Message Retention:** 24 hours
- ✅ **Long Polling:** 20 seconds (reduces API calls)
- ✅ **Dead-Letter Queue:** Configured with 3 retry attempts
- ✅ **DLQ Retention:** 14 days

### Why SQS is the Best Choice

1. **Decoupling:** Separates video upload from processing, enabling independent scaling
2. **Reliability:** Guaranteed message delivery, at-least-once delivery
3. **Scalability:** Automatically handles traffic spikes without provisioning
4. **Cost-Effective:** Pay per request, no idle costs
5. **Dead-Letter Queue:** Captures failed jobs for debugging without losing messages
6. **Integration:** Native integration with S3 events and Lambda

**Alternatives Considered:**
- **SNS:** Pub/sub model, but we need queue semantics for job processing
- **Kinesis:** Overkill for this use case, more expensive, designed for streaming
- **RabbitMQ/Redis:** Requires infrastructure management, no serverless option

### Cost Breakdown

**Assumptions:**
- Videos processed per month: 20 videos
- Messages per video: 1 (job notification)
- DLQ messages: 2 failed jobs/month (10% failure rate)
- API requests: ~500/month (polling, status checks)

**Monthly Costs:**

| Component | Usage | Unit Price | Monthly Cost |
|-----------|-------|------------|--------------|
| **Standard Requests** | 500 requests | First 1M free | **$0.00** |
| **DLQ Requests** | 50 requests | First 1M free | **$0.00** |

**Total SQS Monthly Cost: $0.00 USD** (within free tier)

**Note:** Free tier includes 1 million requests/month. Even at 10x scale (200 videos/month), cost would be $0.00.

**At Scale (10,000 videos/month):**
- Requests: ~250,000/month
- Cost: Still $0.00 (within free tier)

---

## 3. Database: Amazon RDS PostgreSQL

### Configuration

**Resource:** `aws_db_instance.main`  
**Instance Identifier:** `lifestream-db-dev`  
**Engine:** PostgreSQL 15.4  
**Instance Class:** `db.t3.micro`  
**Storage:** 20 GB (gp3)  
**Multi-AZ:** No (dev environment)

**Features Configured:**
- ✅ **Storage Encryption:** Enabled (at-rest encryption)
- ✅ **Backup Retention:** 7 days
- ✅ **Automated Backups:** Enabled (03:00-04:00 UTC)
- ✅ **Maintenance Window:** Monday 04:00-05:00 UTC
- ✅ **CloudWatch Logs:** PostgreSQL and upgrade logs enabled
- ✅ **Publicly Accessible:** No (VPC-only access)
- ✅ **Final Snapshot:** Skipped for dev (enabled for prod)

### Why RDS PostgreSQL is the Best Choice

1. **Managed Service:** No database administration overhead
2. **PostgreSQL:** Open-source, feature-rich, excellent for structured data
3. **Reliability:** Automated backups, point-in-time recovery
4. **Security:** Encryption at rest and in transit, VPC isolation
5. **Scalability:** Easy to upgrade instance class as needed
6. **Cost-Effective:** db.t3.micro is the smallest instance, perfect for dev

**Alternatives Considered:**
- **DynamoDB:** NoSQL, but we need relational data (jobs, summaries, metadata)
- **Aurora Serverless:** More expensive, overkill for dev environment
- **Self-Hosted PostgreSQL:** Requires EC2 management, backups, patching
- **RDS MySQL:** PostgreSQL has better JSON support for our metadata needs

### Cost Breakdown

**Assumptions:**
- Instance running 24/7
- Storage: 20 GB allocated, ~5 GB used
- Backup storage: ~7 GB (7 days retention)
- Data transfer: Minimal (VPC-only)

**Monthly Costs:**

| Component | Usage | Unit Price | Monthly Cost |
|-----------|-------|------------|--------------|
| **db.t3.micro Instance** | 730 hours | $0.017/hour | **$12.41** |
| **Storage (gp3)** | 20 GB | $0.115/GB-month | **$2.30** |
| **Backup Storage** | 7 GB | $0.095/GB-month | **$0.67** |
| **I/O Requests** | ~100K/month | First 3M free | **$0.00** |
| **Data Transfer** | <1 GB | Free (VPC) | **$0.00** |

**Total RDS Monthly Cost: ~$15.38 USD**

**Annual Cost: ~$184.56 USD**

### Cost Optimization Notes

- **Instance Class:** db.t3.micro is the smallest, most cost-effective option
- **Storage:** gp3 is cheaper than io1/io2 and provides better performance
- **Backup Retention:** 7 days is a good balance (could reduce to 3 days to save ~$0.30/month)
- **Multi-AZ:** Disabled for dev (saves 2x instance cost); enable for production

**Production Recommendation:**
- Upgrade to `db.t3.small` (~$24/month) for better performance
- Enable Multi-AZ for high availability (+$24/month)
- Increase backup retention to 30 days (+$2/month)
- **Production Cost: ~$50/month**

---

## 4. Compute: AWS Lambda (Future)

### Configuration (Planned)

**Resource:** Lambda function for video processing  
**Runtime:** Python 3.13  
**Memory:** 3008 MB (maximum)  
**Timeout:** 900 seconds (15 minutes)  
**IAM Role:** `lifestream-lambda-processor-dev`

**Why Lambda is the Best Choice**

1. **Serverless:** No infrastructure management
2. **Cost-Effective:** Pay only for execution time
3. **Auto-Scaling:** Handles concurrent requests automatically
4. **Integration:** Native integration with S3, SQS
5. **Performance:** 3008 MB provides maximum CPU allocation for faster processing

**Alternatives Considered:**
- **ECS/Fargate:** More expensive, requires container management
- **EC2:** Requires instance management, always-on costs
- **Batch:** Overkill for single video processing

### Cost Breakdown (Estimated)

**Assumptions:**
- Videos processed per month: 20 videos
- Average processing time: 10 minutes per video
- Memory: 3008 MB
- Concurrent executions: 1 (sequential processing)

**Monthly Costs:**

| Component | Usage | Calculation | Monthly Cost |
|-----------|-------|-------------|--------------|
| **Compute (GB-seconds)** | 20 videos × 10 min × 3008 MB | 20 × 600 × 2.94 GB = 35,280 GB-s | **$0.59** |
| **Requests** | 20 invocations | First 1M free | **$0.00** |

**Total Lambda Monthly Cost: ~$0.60 USD**

**At Scale (200 videos/month):**
- Compute: ~$5.90/month
- Still very cost-effective

---

## 5. Security: IAM Roles & Policies

### Configuration

**Resource:** `aws_iam_role.lambda_processor`  
**Role Name:** `lifestream-lambda-processor-dev`  
**Trust Policy:** Lambda service principal

**Permissions (Least Privilege):**
- ✅ CloudWatch Logs: Create log groups, streams, put events
- ✅ S3: GetObject, PutObject, DeleteObject, ListBucket (on videos bucket only)
- ✅ SQS: ReceiveMessage, DeleteMessage, GetQueueAttributes, SendMessage (on processing queues only)

### Why This IAM Configuration is the Best Choice

1. **Least Privilege:** Only grants permissions actually needed
2. **Resource-Specific:** ARNs are specific, not wildcards
3. **Service-Specific:** Separate role for Lambda (not shared)
4. **Auditable:** All actions logged in CloudTrail
5. **Secure by Default:** No public access, no overly permissive policies

**Security Best Practices Applied:**
- ✅ No wildcard permissions (`*`)
- ✅ Resource ARNs are explicit
- ✅ Separate role per service
- ✅ No cross-account access
- ✅ No public access policies

### Cost Breakdown

**IAM is FREE** - No charges for IAM roles, policies, or users.

---

## 6. Networking: VPC, Subnets, Security Groups

### Configuration

**VPC:** Default VPC (us-east-1)  
**Subnet Group:** Default subnets across availability zones  
**Security Group:** `lifestream-rds-sg-dev`

**Security Group Rules:**
- ✅ **Ingress:** PostgreSQL (5432) from VPC CIDR only
- ✅ **Egress:** All traffic (for updates, package downloads)

### Why Default VPC is Acceptable for Dev

1. **Simplicity:** No VPC setup required, works out of the box
2. **Cost:** No additional charges for default VPC
3. **Sufficient:** Provides network isolation for dev environment
4. **Easy Migration:** Can move to custom VPC later if needed

**Production Recommendation:**
- Create dedicated VPC with private subnets
- Use NAT Gateway for outbound internet (adds ~$32/month)
- Add VPC endpoints for S3/SQS (reduces NAT Gateway costs)

### Cost Breakdown

**Default VPC: FREE**

**If Using Custom VPC (Production):**
- VPC: Free
- NAT Gateway: ~$32/month + data transfer
- VPC Endpoints: ~$7/month (S3, SQS)
- **Additional Cost: ~$40/month**

---

## 7. Monitoring: CloudWatch & Billing Alerts

### Configuration

**Resource:** `aws_cloudwatch_metric_alarm.billing`  
**Alarm Name:** `lifestream-billing-alert-dev`  
**Threshold:** $50 USD  
**Evaluation Period:** 24 hours  
**Action:** SNS email notification

**SNS Topic:** `lifestream-billing-alerts-dev`  
**Subscription:** Email to `jackiechen486@gmail.com`

### Why CloudWatch Billing Alerts are Essential

1. **Cost Control:** Prevents unexpected charges
2. **Early Warning:** Alerts before costs spiral
3. **Budget Management:** Helps track spending
4. **Free Service:** No additional cost for basic alarms

### Cost Breakdown

**CloudWatch Billing Alarm: FREE**

**SNS Email Notifications: FREE** (for email subscriptions)

**CloudWatch Logs (RDS):**
- Log ingestion: ~100 MB/month
- Storage: ~1 GB/month (7 days retention)
- **Cost: ~$0.50/month**

**Total Monitoring Cost: ~$0.50 USD/month**

---

## 8. Cost Breakdown Summary

### Development Environment (Current)

| Service | Monthly Cost | Annual Cost |
|---------|--------------|-------------|
| **S3 Storage** | $0.25 | $3.00 |
| **SQS Queue** | $0.00 | $0.00 |
| **RDS PostgreSQL** | $15.38 | $184.56 |
| **Lambda (estimated)** | $0.60 | $7.20 |
| **CloudWatch Logs** | $0.50 | $6.00 |
| **IAM, VPC, SNS** | $0.00 | $0.00 |
| **TOTAL** | **$16.73** | **$200.76** |

**Estimated Monthly Cost: $17-25 USD** (with buffer for usage variations)

### Production Environment (Projected)

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| **S3 Storage** | $2.00 | 100 GB storage, higher transfer |
| **SQS Queue** | $0.00 | Still within free tier |
| **RDS PostgreSQL** | $50.00 | db.t3.small, Multi-AZ, 30-day backups |
| **Lambda** | $10.00 | 200 videos/month, optimized |
| **CloudWatch** | $5.00 | Enhanced monitoring |
| **VPC/NAT** | $40.00 | Custom VPC with NAT Gateway |
| **API Gateway** | $3.50 | REST API (1M requests) |
| **TOTAL** | **$110.50** | |

**Estimated Monthly Cost: $100-150 USD** (production with moderate usage)

---

## 9. Cost Optimization Recommendations

### Immediate Optimizations (Dev)

1. **RDS Backup Retention:** Reduce from 7 to 3 days
   - **Savings:** ~$0.30/month

2. **S3 Lifecycle Policy:** Already optimized (30-day deletion)
   - **Current:** Prevents storage bloat

3. **Lambda Memory:** Can reduce to 2048 MB if processing is fast enough
   - **Savings:** ~$0.20/month per video

### Future Optimizations (Production)

1. **Reserved Instances:** Commit to 1-year RDS reservation
   - **Savings:** ~30% (~$15/month for db.t3.small)

2. **S3 Intelligent-Tiering:** Automatic storage class optimization
   - **Savings:** ~10-20% on storage costs

3. **CloudWatch Logs Retention:** Reduce to 3 days for non-critical logs
   - **Savings:** ~$2/month

4. **VPC Endpoints:** Use for S3/SQS to avoid NAT Gateway costs
   - **Savings:** ~$25/month

5. **Spot Instances:** For non-critical processing (if using EC2)
   - **Savings:** Up to 90% (not applicable with Lambda)

### Cost Monitoring

1. **AWS Cost Explorer:** Review monthly spending
2. **Billing Alerts:** Already configured at $50 threshold
3. **Tags:** All resources tagged for cost allocation
4. **Budget:** Set up AWS Budgets for automated alerts

---

## 10. Justification Summary

### Why This Architecture is Optimal

1. **Serverless-First:** Lambda + SQS + S3 = minimal infrastructure management
2. **Cost-Effective:** Pay-per-use model, no idle costs
3. **Scalable:** Auto-scales from 1 to 1000+ videos without changes
4. **Secure:** Encryption, VPC isolation, least-privilege IAM
5. **Reliable:** Managed services with 99.99%+ uptime SLAs
6. **Maintainable:** Infrastructure-as-code, version controlled

### Trade-offs Accepted

1. **Default VPC:** Simpler but less secure than custom VPC (acceptable for dev)
2. **Single-AZ RDS:** Lower cost but no high availability (acceptable for dev)
3. **Standard S3:** Higher cost than Glacier but enables real-time access
4. **db.t3.micro:** Limited performance but sufficient for development

### Production Readiness Checklist

Before moving to production:
- [ ] Upgrade RDS to db.t3.small or larger
- [ ] Enable Multi-AZ for RDS
- [ ] Create custom VPC with private subnets
- [ ] Set up VPC endpoints for S3/SQS
- [ ] Increase backup retention to 30 days
- [ ] Set up CloudWatch dashboards
- [ ] Configure AWS WAF for API protection
- [ ] Enable CloudTrail for audit logging

---

## 11. Additional Considerations

### Data Transfer Costs

**Current Configuration:**
- VPC-to-VPC: Free
- S3 to Lambda: Free (same region)
- Internet egress: Minimal (VPC-only access)

**Production Considerations:**
- API responses: ~$0.09/GB (first 10 TB free)
- Video downloads: Consider CloudFront CDN for cost optimization

### Free Tier Benefits

**AWS Free Tier (12 months for new accounts):**
- RDS: 750 hours/month of db.t2.micro (we're using db.t3.micro, so no free tier)
- S3: 5 GB storage, 20,000 GET requests
- Lambda: 1M requests, 400,000 GB-seconds
- SQS: 1M requests

**Our Usage:**
- S3: Within free tier (5 GB)
- Lambda: Within free tier
- SQS: Within free tier
- RDS: Not eligible (db.t3.micro not in free tier)

**Potential Savings:** ~$12/month if using db.t2.micro (but t3.micro is better performance)

---

## 12. Cost Comparison: Alternatives

### Alternative 1: Self-Hosted (EC2 + PostgreSQL)

| Component | Monthly Cost |
|-----------|--------------|
| EC2 t3.medium | $30.00 |
| EBS 50 GB | $5.00 |
| Data Transfer | $5.00 |
| **TOTAL** | **$40.00** |

**Verdict:** More expensive, requires management, less scalable

### Alternative 2: Serverless Database (DynamoDB)

| Component | Monthly Cost |
|-----------|--------------|
| DynamoDB (On-Demand) | $1.25 per million reads |
| Storage | $0.25/GB |
| **TOTAL** | **~$10-20** |

**Verdict:** Cheaper but less suitable for relational data

### Alternative 3: Container-Based (ECS Fargate)

| Component | Monthly Cost |
|-----------|--------------|
| Fargate (0.5 vCPU, 1 GB) | $15.00 |
| ECS Tasks | $0.04/hour |
| **TOTAL** | **~$30-40** |

**Verdict:** More expensive, requires container management

**Conclusion:** Current architecture (RDS + Lambda + S3) is optimal for cost, scalability, and management overhead.

---

## 13. References

- [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/)
- [AWS RDS Pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [AWS SQS Pricing](https://aws.amazon.com/sqs/pricing/)
- [AWS Free Tier](https://aws.amazon.com/free/)

**Last Updated:** 2026-01-20  
**Pricing Source:** AWS Pricing Calculator & Official AWS Documentation (2024-2025)

---

## Appendix: Cost Estimation Methodology

### Assumptions Used

1. **Video Processing:**
   - Average video: 1 hour, 500 MB compressed
   - Processing time: 10 minutes per video
   - 20 videos/month (development)

2. **Storage:**
   - Videos stored for 30 days (lifecycle policy)
   - Average storage: 10 GB

3. **Database:**
   - 5 GB used storage
   - 7 GB backup storage (7-day retention)
   - Low I/O (development workload)

4. **Region:**
   - us-east-1 (N. Virginia) - lowest cost region

### Cost Calculation Formula

**RDS Cost:**
```
Instance Cost = (Instance Price/Hour) × 730 hours
Storage Cost = (Allocated GB) × (Price/GB-month)
Backup Cost = (Backup GB) × (Backup Price/GB-month)
Total = Instance + Storage + Backup
```

**Lambda Cost:**
```
Compute Cost = (GB-seconds) × ($0.0000166667/GB-second)
Requests Cost = (Requests - 1M free) × ($0.20/1M)
Total = Compute + Requests
```

**S3 Cost:**
```
Storage Cost = (GB stored) × ($0.023/GB-month)
Request Cost = (Requests/1000) × (Price per 1K)
Total = Storage + Requests
```

---

**Document Status:** Complete  
**Next Review:** After first month of usage to validate estimates
