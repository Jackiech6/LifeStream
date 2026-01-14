# LifeStream Intelligent Diary

An automated multi-modal pipeline that converts raw video footage into structured, searchable daily journals and meeting minutes.

## Project Status

**Current Stage:** Stage 1 - Core Processing Engine  
**Duration:** 3 Weeks Total (1 week per stage)

## Quick Start (Mac)

### Prerequisites

- macOS (tested on macOS 13+)
- Python 3.10+ (install via Homebrew: `brew install python@3.11`)
- FFmpeg (install via Homebrew: `brew install ffmpeg`)
- HuggingFace account (for diarization models)
- OpenAI API key (or alternative LLM provider)

### Setup

1. **Install Homebrew** (if not already installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install FFmpeg**:
   ```bash
   brew install ffmpeg
   ```

3. **Clone/navigate to the repository**:
   ```bash
   cd ~/Desktop/LifeStream
   ```

4. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

6. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   nano .env  # or use your preferred editor
   ```

7. **Run the pipeline**:
   ```bash
   python src/main.py --input ~/Videos/meeting.mp4 --output summary.md
   ```

For detailed Mac-specific setup instructions, see [LOCAL_SETUP.md](./LOCAL_SETUP.md)

## Project Structure

See `STAGE1_IMPLEMENTATION_PLAN.md` for detailed architecture and implementation details.

## Stages Overview

- **Stage 1:** Core Processing Engine (Video → Markdown)
- **Stage 2:** Memory, Search & Intelligence (RAG Implementation)
- **Stage 3:** Cloud Deployment & Productization (Web Interface)

## Documentation

- [Stage 1 Implementation Plan](./STAGE1_IMPLEMENTATION_PLAN.md) - Detailed implementation guide
- [Local Mac Setup Guide](./LOCAL_SETUP.md) - Mac-specific setup instructions

## License

Internal project - Onboarding training
