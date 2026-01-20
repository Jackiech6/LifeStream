# RDS PostgreSQL Configuration & Scaling Guide

**Date:** 2026-01-20  
**Instance:** `lifestream-db-dev`  
**Engine:** PostgreSQL 15.4

---

## 📋 Current Configuration

### Instance Specifications

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Instance Class** | `db.t3.micro` | Burstable performance instance |
| **vCPU** | 2 vCPUs | Virtual CPUs available |
| **Memory (RAM)** | 1 GB | Available memory |
| **Storage Type** | `gp3` (General Purpose SSD) | Storage type |
| **Allocated Storage** | 20 GB | Initial storage allocation |
| **Storage Encryption** | ✅ Enabled | Encryption at rest |
| **Multi-AZ** | ❌ Disabled | Single availability zone (dev) |
| **Backup Retention** | 7 days | Automated backup retention |
| **Public Access** | ❌ No | VPC-only access |

### Configuration Details

**Terraform Configuration:**
```hcl
resource "aws_db_instance" "main" {
  identifier        = "lifestream-db-dev"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true
  
  db_name  = "lifestream"
  username = "lifestream_admin"
  password = var.db_password
  
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"
  
  skip_final_snapshot = true  # For dev environment
}
```

**Location:** `infrastructure/main.tf` (lines 290-310)

---

## 🔍 Instance Capacity Limits

### db.t3.micro Specifications

**Compute Resources:**
- **vCPUs:** 2 (burstable)
- **Memory:** 1 GB RAM
- **Network Performance:** Up to 5 Gbps
- **Baseline Performance:** 20% CPU (burstable)
- **Burst Performance:** Up to 100% CPU (uses CPU credits)

**Storage:**
- **Storage Type:** gp3 (General Purpose SSD)
- **Baseline IOPS:** 3,000 IOPS (for gp3)
- **Maximum IOPS:** 16,000 IOPS (can be provisioned)
- **Throughput:** 125 MB/s baseline, up to 1,000 MB/s

**CPU Credits:**
- **Accrual Rate:** 6 credits/hour
- **Maximum Credits:** 72 credits
- **Burst Duration:** ~36 minutes at 100% CPU (if fully charged)

### What Happens When Capacity is Exceeded?

#### 1. **CPU Capacity Exceeded**

**Scenario:** Sustained high CPU usage (>20% baseline)

**What Happens:**
- Instance uses **CPU credits** for burst performance
- When credits are exhausted, CPU is throttled to baseline (20%)
- Performance degrades significantly
- Database queries become slow
- Application may experience timeouts

**Symptoms:**
- Slow query execution
- High `CPUUtilization` CloudWatch metric
- `CPUCreditBalance` drops to near zero
- Application errors/timeouts

**Monitoring:**
- CloudWatch metric: `CPUUtilization` (should stay <80% average)
- CloudWatch metric: `CPUCreditBalance` (should stay >20 credits)

#### 2. **Memory Capacity Exceeded**

**Scenario:** Database uses more than 1 GB RAM

**What Happens:**
- PostgreSQL uses **swap space** (disk-based memory)
- Severe performance degradation (100-1000x slower)
- Query performance drops dramatically
- Possible connection failures
- Risk of OOM (Out of Memory) errors

**Symptoms:**
- Extremely slow queries
- High disk I/O
- Connection timeouts
- Database errors

**Monitoring:**
- CloudWatch metric: `FreeableMemory` (should stay >200 MB)
- PostgreSQL query: `SELECT * FROM pg_stat_database;`

#### 3. **Storage Capacity Exceeded**

**Scenario:** Database grows beyond 20 GB

**What Happens:**
- **Without Auto-Scaling:** Database becomes read-only when storage is full
- **With Auto-Scaling:** Storage automatically increases (if configured)
- Writes fail when storage is 100% full
- Database may become unavailable

**Symptoms:**
- "Disk full" errors
- Write operations fail
- Database becomes read-only
- Application errors

**Monitoring:**
- CloudWatch metric: `FreeStorageSpace` (should stay >2 GB)
- CloudWatch metric: `FreeableStorage` (percentage)

#### 4. **I/O Capacity Exceeded**

**Scenario:** High disk I/O operations

**What Happens:**
- I/O operations queue up
- Query performance degrades
- Latency increases
- Possible connection timeouts

**Symptoms:**
- Slow read/write operations
- High `ReadLatency` / `WriteLatency`
- Database appears "stuck"

**Monitoring:**
- CloudWatch metric: `ReadIOPS` / `WriteIOPS`
- CloudWatch metric: `ReadLatency` / `WriteLatency`

---

## 📊 Capacity Planning

### Expected Usage (Development)

**Typical Workload:**
- **Database Size:** ~1-5 GB (metadata, summaries, chunks)
- **Concurrent Connections:** 5-10
- **Queries per Second:** 10-50
- **CPU Usage:** 10-30% average
- **Memory Usage:** 400-800 MB

**Current Capacity:**
- ✅ **Storage:** 20 GB (sufficient for months of dev data)
- ✅ **Memory:** 1 GB (adequate for small workloads)
- ⚠️ **CPU:** 2 vCPUs burstable (may need upgrade for heavy processing)
- ✅ **I/O:** 3,000 IOPS (sufficient for typical workloads)

### Warning Thresholds

Set CloudWatch alarms for:
- **CPU Utilization:** >70% for 5 minutes
- **CPU Credit Balance:** <20 credits
- **Free Memory:** <200 MB
- **Free Storage:** <2 GB (10% of 20 GB)
- **Read Latency:** >200 ms
- **Write Latency:** >100 ms

---

## 🚀 How to Scale Up

### Option 1: Upgrade Instance Class (Vertical Scaling)

**When to Use:**
- CPU or memory is the bottleneck
- Consistent high CPU usage (>50%)
- Memory pressure (frequent swapping)
- Need better network performance

**Steps:**

#### Via Terraform (Recommended)

1. **Update `terraform.tfvars`:**
   ```hcl
   db_instance_class = "db.t3.small"  # or db.t3.medium, db.t3.large
   ```

2. **Apply changes:**
   ```bash
   cd infrastructure
   export AWS_PROFILE=dev
   terraform plan  # Review changes
   terraform apply # Apply upgrade
   ```

3. **Downtime:** ~5-15 minutes (instance reboot required)

#### Via AWS Console

1. Go to RDS → Databases → Select `lifestream-db-dev`
2. Click **Modify**
3. Change **DB instance class** to larger size
4. Choose **Apply immediately** or **During maintenance window**
5. Review and confirm

#### Via AWS CLI

```bash
aws rds modify-db-instance \
  --db-instance-identifier lifestream-db-dev \
  --db-instance-class db.t3.small \
  --apply-immediately
```

**Instance Class Options:**

| Instance Class | vCPU | Memory | Monthly Cost | Use Case |
|----------------|------|--------|--------------|----------|
| `db.t3.micro` | 2 | 1 GB | ~$15 | **Current** - Dev/test |
| `db.t3.small` | 2 | 2 GB | ~$30 | Small production |
| `db.t3.medium` | 2 | 4 GB | ~$60 | Medium workloads |
| `db.t3.large` | 2 | 8 GB | ~$120 | Large workloads |
| `db.m5.large` | 2 | 8 GB | ~$150 | Production (non-burstable) |
| `db.m5.xlarge` | 4 | 16 GB | ~$300 | High-performance |

**Recommendation:** Start with `db.t3.small` for production, upgrade to `db.m5.large` if consistent performance needed.

---

### Option 2: Increase Storage

**When to Use:**
- Running out of storage space
- Need more storage for data growth
- Want to enable storage auto-scaling

**Steps:**

#### Via Terraform

1. **Update `terraform.tfvars`:**
   ```hcl
   db_allocated_storage = 50  # Increase from 20 to 50 GB
   ```

2. **Apply:**
   ```bash
   terraform apply
   ```

**Note:** Storage can only be **increased**, never decreased. Must increase by at least 10%.

#### Via AWS Console

1. RDS → Databases → Modify
2. Change **Allocated storage** (minimum 10% increase)
3. Apply changes

**Storage Scaling:**
- ✅ **No downtime** (storage expansion is online)
- ✅ **Automatic optimization** after expansion
- ⚠️ **Cannot decrease** storage size
- ✅ **Can enable auto-scaling** to prevent future issues

---

### Option 3: Enable Storage Auto-Scaling

**When to Use:**
- Want automatic storage expansion
- Prevent storage-related outages
- Handle unpredictable growth

**Configuration:**

Add to `infrastructure/main.tf`:

```hcl
resource "aws_db_instance" "main" {
  # ... existing configuration ...
  
  # Enable storage auto-scaling
  max_allocated_storage = 100  # Maximum storage limit (GB)
  
  # Or use the newer syntax:
  storage_autoscaling {
    enabled = true
    max_capacity = 100  # GB
  }
}
```

**How It Works:**
- Monitors free storage space
- Triggers when free space ≤ 10% for 5 minutes
- Increases storage by 10% or 10 GB (whichever is larger)
- Stops at `max_allocated_storage` limit
- No downtime during expansion

**Cost Impact:** Only pay for storage actually used.

---

### Option 4: Upgrade to Provisioned IOPS

**When to Use:**
- I/O performance is the bottleneck
- Need consistent, low-latency I/O
- High transaction workloads

**Configuration:**

```hcl
resource "aws_db_instance" "main" {
  # ... existing configuration ...
  
  storage_type      = "io2"  # or "io1"
  iops              = 3000    # IOPS (minimum depends on storage size)
  allocated_storage = 100     # Must be at least 100 GB for io2
}
```

**IOPS Options:**
- **gp3:** 3,000 baseline IOPS (current), up to 16,000
- **io1/io2:** 1,000-256,000 IOPS (provisioned)

**Cost:** Higher than gp3, but better performance.

---

### Option 5: Enable Multi-AZ (High Availability)

**When to Use:**
- Production environment
- Need high availability
- Want zero-downtime maintenance
- Disaster recovery requirements

**Configuration:**

```hcl
resource "aws_db_instance" "main" {
  # ... existing configuration ...
  
  multi_az = true  # Enable Multi-AZ deployment
}
```

**Benefits:**
- Automatic failover (1-2 minutes)
- Zero-downtime maintenance
- Synchronous replication
- Enhanced durability

**Cost:** ~2x instance cost (standby replica in another AZ)

---

### Option 6: Create Read Replicas (Horizontal Scaling)

**When to Use:**
- Read-heavy workloads
- Need to offload read queries
- Geographic distribution
- Disaster recovery

**Configuration:**

```hcl
resource "aws_db_instance" "read_replica" {
  identifier     = "lifestream-db-dev-replica"
  replicate_source_db = aws_db_instance.main.identifier
  instance_class = "db.t3.micro"
  
  # Can be in different region
  availability_zone = "us-east-1b"
}
```

**Benefits:**
- Offload read queries
- Geographic distribution
- Disaster recovery
- Can promote to primary if needed

**Cost:** Same as primary instance (pay for replica)

---

## 📈 Scaling Strategy Recommendations

### Development Environment

**Current Setup:** ✅ Appropriate
- `db.t3.micro` is sufficient for development
- 20 GB storage is plenty
- No need for Multi-AZ or read replicas

**When to Scale:**
- If CPU consistently >50%
- If memory usage >800 MB
- If storage >15 GB

**Recommended Upgrade Path:**
1. `db.t3.micro` → `db.t3.small` (if CPU/memory pressure)
2. Enable storage auto-scaling (max 50 GB)
3. Monitor CloudWatch metrics

### Production Environment

**Recommended Initial Setup:**
- **Instance Class:** `db.t3.small` or `db.m5.large`
- **Storage:** 100 GB with auto-scaling (max 500 GB)
- **Multi-AZ:** Enabled
- **Backup Retention:** 30 days
- **Read Replicas:** 1-2 (if read-heavy)

**Scaling Plan:**
1. Start with `db.t3.small` (or `db.m5.large` for consistent performance)
2. Enable storage auto-scaling
3. Enable Multi-AZ for high availability
4. Add read replicas if read-heavy
5. Monitor and adjust based on metrics

---

## 🔧 Monitoring & Alerts

### Essential CloudWatch Metrics

**CPU & Memory:**
- `CPUUtilization` - Target: <70%
- `CPUCreditBalance` - Target: >20 credits
- `FreeableMemory` - Target: >200 MB

**Storage:**
- `FreeStorageSpace` - Target: >2 GB
- `FreeableStorage` - Target: >10%

**I/O:**
- `ReadLatency` - Target: <200 ms
- `WriteLatency` - Target: <100 ms
- `ReadIOPS` / `WriteIOPS` - Monitor trends

**Connections:**
- `DatabaseConnections` - Monitor for connection pool issues

### Setting Up Alarms

**Terraform Configuration:**

```hcl
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "lifestream-db-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "RDS CPU utilization is high"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
}
```

---

## 💰 Cost Impact of Scaling

### Current Cost (db.t3.micro)
- **Instance:** ~$15/month
- **Storage (20 GB):** ~$2.30/month
- **Backups (7 GB):** ~$0.67/month
- **Total:** ~$18/month

### Scaling Costs

| Upgrade | Instance Cost | Storage Cost | Total |
|---------|---------------|--------------|-------|
| `db.t3.small` | ~$30/month | ~$2.30/month | ~$32/month |
| `db.t3.medium` | ~$60/month | ~$2.30/month | ~$62/month |
| `db.m5.large` | ~$150/month | ~$2.30/month | ~$152/month |
| Multi-AZ (2x) | 2x instance cost | Same storage | ~$36-304/month |

**Storage Auto-Scaling:** Only pay for storage actually used (no additional cost for the feature).

---

## ✅ Quick Reference: Scaling Commands

### Check Current Status
```bash
aws rds describe-db-instances \
  --db-instance-identifier lifestream-db-dev \
  --query 'DBInstances[0].{Class:DBInstanceClass,Storage:AllocatedStorage,Status:DBInstanceStatus}'
```

### Upgrade Instance Class
```bash
aws rds modify-db-instance \
  --db-instance-identifier lifestream-db-dev \
  --db-instance-class db.t3.small \
  --apply-immediately
```

### Increase Storage
```bash
aws rds modify-db-instance \
  --db-instance-identifier lifestream-db-dev \
  --allocated-storage 50 \
  --apply-immediately
```

### Enable Multi-AZ
```bash
aws rds modify-db-instance \
  --db-instance-identifier lifestream-db-dev \
  --multi-az \
  --apply-immediately
```

---

## 🎯 Summary

**Current Configuration:**
- ✅ `db.t3.micro` - Appropriate for development
- ✅ 20 GB storage - Sufficient for dev workloads
- ✅ gp3 storage - Good performance/cost balance
- ⚠️ Single AZ - Acceptable for dev, upgrade for prod

**When Capacity is Exceeded:**
- CPU: Throttled to baseline (slow queries)
- Memory: Swap usage (severe degradation)
- Storage: Read-only mode (writes fail)
- I/O: Queued operations (high latency)

**Scaling Options:**
1. **Vertical:** Upgrade instance class (CPU/memory)
2. **Storage:** Increase allocated storage
3. **Auto-Scaling:** Enable automatic storage expansion
4. **High Availability:** Enable Multi-AZ
5. **Horizontal:** Add read replicas

**Recommended Next Steps:**
1. Set up CloudWatch alarms for capacity metrics
2. Monitor usage for 1-2 weeks
3. Enable storage auto-scaling (max 50 GB for dev)
4. Plan production upgrade to `db.t3.small` or `db.m5.large` with Multi-AZ

---

**Last Updated:** 2026-01-20  
**Document Version:** 1.0
