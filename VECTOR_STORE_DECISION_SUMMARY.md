# Vector Store Selection: FAISS vs Pinecone - Decision Summary

**Date:** 2026-01-20

---

## Quick Answer

**Currently, Pinecone is used by default** because:
- ✅ Pinecone API key is configured in `.env`
- ✅ Factory function auto-selects Pinecone when API key is present
- ✅ This is appropriate for Stage 3 (cloud deployment)

---

## How Selection Works

### Automatic Selection (Default)

The `create_vector_store()` factory function automatically chooses:

```python
from src.memory.store_factory import create_vector_store
from config.settings import Settings

settings = Settings()
store = create_vector_store(settings)  # Auto-selects
```

**Selection Logic:**
1. **Check `settings.vector_store_type`** (if set to "pinecone" or "faiss", use that)
2. **If "auto" or not set:**
   - ✅ **Pinecone API key present** → Use Pinecone
   - ❌ **No Pinecone API key** → Use FAISS

### Your Current Configuration

```bash
# In .env:
PINECONE_API_KEY=pcsk_...  # ✅ Configured
VECTOR_STORE_TYPE=auto      # Default (auto-select)
```

**Result:** Pinecone is automatically selected

---

## When Each Store is Used

### Pinecone (Current Default)

**Used when:**
- Pinecone API key is configured ✅ (your case)
- `VECTOR_STORE_TYPE=pinecone` is set
- `force_type="pinecone"` is passed

**Best for:**
- Production/cloud deployment
- Shared access across multiple workers
- Scalable, managed service

### FAISS

**Used when:**
- No Pinecone API key configured
- `VECTOR_STORE_TYPE=faiss` is set
- `force_type="faiss"` is passed

**Best for:**
- Local development
- Testing without cloud dependencies
- Offline work

---

## How to Change Selection

### Option 1: Remove Pinecone API Key (Use FAISS)

```bash
# In .env, comment out or remove:
# PINECONE_API_KEY=pcsk_...
```

Result: Factory will auto-select FAISS

### Option 2: Explicit Setting

```bash
# In .env:
VECTOR_STORE_TYPE=faiss  # Force FAISS
# or
VECTOR_STORE_TYPE=pinecone  # Force Pinecone
```

### Option 3: Code-Level Override

```python
# Force FAISS
store = create_vector_store(settings, force_type="faiss")

# Force Pinecone
store = create_vector_store(settings, force_type="pinecone")
```

---

## Verification

**Check which store will be used:**
```python
from src.memory.store_factory import get_vector_store_type
from config.settings import Settings

print(get_vector_store_type(Settings()))  # "pinecone" or "faiss"
```

**Current result:** `"pinecone"` (because API key is configured)

---

## Summary

| Question | Answer |
|----------|--------|
| **Is Pinecone used by default?** | ✅ Yes (when API key is configured) |
| **Is FAISS still available?** | ✅ Yes (as fallback or explicit choice) |
| **How to switch?** | Remove API key or set `VECTOR_STORE_TYPE=faiss` |
| **Which should I use?** | Pinecone for Stage 3 (cloud), FAISS for local dev |

---

**Last Updated:** 2026-01-20
