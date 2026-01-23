# Summarization Fix Summary

## Problem

Video summaries were showing generic, useless content:
- **Activity:** "Activity" (placeholder)
- **Participants:** "unknown: unknown"
- **Source Reliability:** Low
- Time blocks like "00:00 - 00:01" for 2‑minute videos (seconds dropped)

Summarization worked in Stage 1 (local) but regressed in the deployed pipeline.

## Root Causes

1. **Generic "Activity"**  
   LLM sometimes returned "Activity", or parsing failed and we fell back to the default. The default timeblock always used `activity="Activity"`.

2. **No transcript-based fallback**  
   When the LLM failed or returned generic text, we didn’t use available transcript content to derive a meaningful activity.

3. **"unknown: unknown"**  
   Participants were created with only `speaker_id` (e.g. `"unknown"` from ASR‑only). `real_name` was left unset, and the UI showed "unknown: unknown".

4. **Time format**  
   `_format_time_string` used `HH:MM` only, so 97 seconds showed as "00:00 - 00:01" instead of "00:00:00 - 00:01:37".

5. **Weak handling of no-speech**  
   When there was no audio, we still called the LLM with "[No audio segments...]" and often got generic output. We didn’t explicitly use "No speech detected" or similar.

## Fixes Applied

### 1. Summarization (`src/processing/summarization.py`)

- **System prompt**  
  - Instruct the LLM to never use "Activity" as the activity.  
  - Use "No speech detected" when there’s no speech and briefly describe visuals.

- **`_create_prompt`**  
  - Use `"[No audio segments in this time window — no speech detected]"` when there are no segments.

- **`_format_time_string`**  
  - Switch to `HH:MM:SS` (e.g. `00:01:37` for 97 seconds).

- **`_activity_from_transcript`**  
  - New helper to derive a short activity from context transcript (first ~80 chars) when the LLM is generic or fails.

- **`_parse_llm_response`**  
  - Also extract activity from the `**Activity:**` line.  
  - If parsed activity is "Activity" or missing, use `_activity_from_transcript` or "No speech detected".  
  - Set `real_name=speaker_id` for participants (use "Unidentified speaker" when `speaker_id` is `"unknown"` / `"Speaker_Unknown"`).  
  - More robust extraction of transcript summary (same‑line or following lines).

- **`_create_default_timeblock`**  
  - Use transcript‑derived activity when available.  
  - Otherwise use "No speech detected" or "Visual segment only".  
  - Same participant `real_name` handling as above.

- **Fast path**  
  - If context has neither audio nor video, skip the LLM and create a default timeblock (avoids useless API calls).

### 2. Data Models (`src/models/data_models.py`)

- **`to_markdown`**  
  - When rendering participants, if `real_name` or `speaker_id` is `"unknown"` or `"Speaker_Unknown"`, display "Unidentified speaker" instead of "unknown: unknown".

### 3. Chunking (`src/memory/chunking.py`)

- **`_parse_time_to_seconds`**  
  - Support `HH:MM:SS` in addition to `HH:MM`, so chunking works correctly with the new time format.

### 4. Processor Lambda (`infrastructure/lambda.tf`)

- **`WHISPER_CACHE_DIR`**  
  - Set to `"/tmp/whisper_cache"` so Whisper uses `/tmp` in Lambda and avoids read‑only filesystem issues.

### 5. Tests & Frontend

- **`tests/unit/test_summarization.py`**  
  - Updated for new default timeblock behavior and `HH:MM:SS` formatting.

- **`frontend/lib/types.ts`**  
  - Document that `start_time` / `end_time` can be `"HH:MM:SS"`.

## What You Need To Do

1. **Redeploy processor Lambda**  
   - Rebuild and push the processor Docker image.  
   - Run `terraform apply` so the new `WHISPER_CACHE_DIR` (and any image updates) are applied.

2. **Re-run processing for existing videos (optional)**  
   - Old summaries in S3/RDS were generated with the previous logic.  
   - To get improved summaries, re-upload those videos or re-trigger processing so they go through the new pipeline.

3. **Verify**  
   - Upload a new test video.  
   - Check that summaries have non‑generic activities, proper participant labels, and correct `HH:MM:SS` time blocks.

## Files Touched

- `src/processing/summarization.py`
- `src/models/data_models.py`
- `src/memory/chunking.py`
- `infrastructure/lambda.tf`
- `tests/unit/test_summarization.py`
- `frontend/lib/types.ts`
