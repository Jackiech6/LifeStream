# Vector Store Selection Guide: FAISS vs Pinecone

**Date:** 2026-01-20  
**Purpose:** Explains when and how to use FAISS vs Pinecone in LifeStream

---

## Overview

LifeStream supports two vector store implementations:
- **FAISS** - Local, file-based storage (Stage 2)
- **Pinecone** - Managed cloud storage (Stage 3)

Both implement the same `VectorStore` protocol, so your code doesn't need to change when switching between them.

---

## Automatic Selection Logic

The `create_vector_store()` factory function automatically chooses the best option:

### Default Behavior (Auto Mode)

```python
from src.memory.store_factory import create_vector_store
from config.settings import Settings

settings = Settings()
store = create_vector_store(settings)  # Auto-selects
```

**Selection Rules:**
1. **If Pinecone API key is configured** → Uses Pinecone (cloud/production)
2. **If no Pinecone API key** → Uses FAISS (local development)
3. **If Pinecone unavailable but API key present** → Falls back to FAISS with warning

### Current Configuration

Based on your `.env` file:
- ✅ Pinecone API key is configured
- **Default selection:** **Pinecone** (cloud storage)

---

## When to Use Each

### Use FAISS When:

- ✅ **Local development** - Testing without cloud dependencies
- ✅ **Offline work** - No internet connection required
- ✅ **Cost concerns** - Free, no API costs
- ✅ **Quick prototyping** - No account setup needed
- ✅ **Small datasets** - Works well for development/testing

**Example:**
```python
from src.memory.store_factory import create_vector_store
from config.settings import Settings

settings = Settings()
settings.pinecone_api_key = None  # Disable Pinecone
store = create_vector_store(settings)  # Will use FAISS
```

### Use Pinecone When:

- ✅ **Production deployment** - Scalable, managed service
- ✅ **Cloud infrastructure** - Part of Stage 3 deployment
- ✅ **Multiple workers** - Shared index across Lambda functions
- ✅ **Large datasets** - Handles millions of vectors
- ✅ **High availability** - Managed service with uptime SLA
- ✅ **Auto-scaling** - Serverless, scales automatically

**Example:**
```python
from src.memory.store_factory import create_vector_store
from config.settings import Settings

settings = Settings()  # Pinecone API key from .env
store = create_vector_store(settings)  # Will use Pinecone
```

---

## Manual Selection

You can explicitly force a specific store type:

### Force Pinecone

```python
store = create_vector_store(settings, force_type="pinecone")
```

**Requirements:**
- Pinecone API key must be configured
- Pinecone package must be installed

### Force FAISS

```python
store = create_vector_store(settings, force_type="faiss")
```

**Requirements:**
- FAISS package must be installed (`faiss-cpu`)

---

## Configuration Settings

### Environment Variables

Add to `.env`:

```bash
# Vector Store Selection
VECTOR_STORE_TYPE=auto  # auto, pinecone, or faiss

# Pinecone Configuration (if using Pinecone)
PINECONE_API_KEY=pcsk_...
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=lifestream-dev

# FAISS Configuration (if using FAISS)
VECTOR_STORE_INDEX_DIR=memory_index  # Directory for FAISS index files
```

### Settings Options

```python
class Settings:
    # Vector Store Selection
    vector_store_type: str = "auto"  # auto, pinecone, or faiss
    vector_store_index_dir: str = "memory_index"  # For FAISS
    
    # Pinecone (if using Pinecone)
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "lifestream-dev"
```

---

## Usage Examples

### Example 1: Auto-Selection (Recommended)

```python
from src.memory.store_factory import create_vector_store
from src.memory.index_builder import index_daily_summary
from src.memory.embeddings import OpenAIEmbeddingModel
from config.settings import Settings

settings = Settings()
store = create_vector_store(settings)  # Auto-selects based on config
embedder = OpenAIEmbeddingModel(settings)

# Index a summary (works with either store)
index_daily_summary(daily_summary, store, embedder)
```

### Example 2: Explicit Pinecone (Production)

```python
from src.memory.store_factory import create_vector_store
from config.settings import Settings

settings = Settings()
# Ensure Pinecone is used
store = create_vector_store(settings, force_type="pinecone")
```

### Example 3: Explicit FAISS (Local Development)

```python
from src.memory.store_factory import create_vector_store
from config.settings import Settings

settings = Settings()
# Force FAISS for local testing
store = create_vector_store(settings, force_type="faiss", index_dir="local_index")
```

### Example 4: Check Which Store Will Be Used

```python
from src.memory.store_factory import get_vector_store_type
from config.settings import Settings

settings = Settings()
store_type = get_vector_store_type(settings)
print(f"Will use: {store_type}")  # "pinecone" or "faiss"
```

---

## Migration Between Stores

### From FAISS to Pinecone

1. **Configure Pinecone API key:**
   ```bash
   echo "PINECONE_API_KEY=pcsk_..." >> .env
   ```

2. **Run migration script (optional):**
   ```bash
   python scripts/migrate_faiss_to_pinecone.py
   ```

3. **Use factory function:**
   ```python
   store = create_vector_store(settings)  # Will now use Pinecone
   ```

### From Pinecone to FAISS

1. **Remove or comment out Pinecone API key:**
   ```bash
   # PINECONE_API_KEY=pcsk_...
   ```

2. **Or explicitly force FAISS:**
   ```python
   store = create_vector_store(settings, force_type="faiss")
   ```

---

## Decision Matrix

| Scenario | Recommended Store | Reason |
|----------|------------------|--------|
| **Local development** | FAISS | No cloud dependencies, free |
| **Production deployment** | Pinecone | Scalable, managed, shared access |
| **Testing/CI** | FAISS | Fast, no external dependencies |
| **Multi-user system** | Pinecone | Shared index, concurrent access |
| **Offline development** | FAISS | No internet required |
| **Large scale (1M+ vectors)** | Pinecone | Better performance, managed |
| **Cost-sensitive dev** | FAISS | Free, no API costs |
| **Cloud-native architecture** | Pinecone | Integrates with AWS/Lambda |

---

## Current Default Behavior

**Based on your configuration:**

```python
# Your .env has:
PINECONE_API_KEY=pcsk_...  # ✅ Configured

# Therefore:
store = create_vector_store(settings)
# → Will use PineconeVectorStore
```

**To verify:**
```python
from src.memory.store_factory import get_vector_store_type
from config.settings import Settings

print(get_vector_store_type(Settings()))  # Should print "pinecone"
```

---

## Troubleshooting

### Issue: "Pinecone API key required"

**Solution:** Either:
1. Add `PINECONE_API_KEY` to `.env`, OR
2. Use FAISS: `create_vector_store(settings, force_type="faiss")`

### Issue: "FAISS not available"

**Solution:** Install FAISS:
```bash
pip install faiss-cpu
```

### Issue: "Pinecone not available"

**Solution:** Install Pinecone:
```bash
pip install pinecone
```

### Issue: Want to use FAISS despite Pinecone API key

**Solution:** Explicitly force FAISS:
```python
store = create_vector_store(settings, force_type="faiss")
```

Or set in `.env`:
```bash
VECTOR_STORE_TYPE=faiss
```

---

## Best Practices

1. **Use factory function** - Don't instantiate stores directly
   ```python
   # ✅ Good
   store = create_vector_store(settings)
   
   # ❌ Avoid (unless you have a specific reason)
   store = PineconeVectorStore(settings)
   ```

2. **Let auto-selection work** - Only override when necessary
   ```python
   # ✅ Good - auto-selects based on config
   store = create_vector_store(settings)
   
   # ✅ Good - explicit when needed
   store = create_vector_store(settings, force_type="faiss")
   ```

3. **Check store type in logs** - Factory logs which store is selected
   ```python
   store = create_vector_store(settings)
   # Logs: "Auto-selected PineconeVectorStore (API key configured)"
   ```

4. **Use same interface** - Code works with both stores
   ```python
   # This works with FAISS or Pinecone
   index_daily_summary(summary, store, embedder)
   semantic_search(query, store, embedder)
   ```

---

## Summary

**Current Setup:**
- ✅ Pinecone API key configured → **Pinecone is default**
- ✅ Factory function available → **Automatic selection**
- ✅ Both stores available → **Easy switching**

**To Use:**
```python
from src.memory.store_factory import create_vector_store
store = create_vector_store(settings)  # Automatically uses Pinecone
```

**To Switch:**
- Remove Pinecone API key → Falls back to FAISS
- Or set `VECTOR_STORE_TYPE=faiss` in `.env`
- Or use `force_type="faiss"` parameter

---

**Last Updated:** 2026-01-20
