# Local Mac Development Setup Guide

This guide provides detailed instructions for setting up the LifeStream project on your Mac laptop for local development.

## System Requirements

- **macOS:** 13.0 (Ventura) or later (tested on macOS 14+)
- **Python:** 3.10 or higher
- **RAM:** 8GB minimum (16GB recommended for large videos)
- **Storage:** At least 10GB free space (for models and temporary files)
- **Internet:** Required for initial model downloads and API calls

## Step-by-Step Setup

### 1. Install Homebrew

Homebrew is a package manager for macOS. If you don't have it installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions. After installation, you may need to add Homebrew to your PATH:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Verify installation:
```bash
brew --version
```

### 2. Install FFmpeg

FFmpeg is required for video and audio processing:

```bash
brew install ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

You should see version information. If you get "command not found", ensure Homebrew's bin directory is in your PATH.

### 3. Install Python 3.10+

Check your current Python version:
```bash
python3 --version
```

If you need to install or upgrade Python:
```bash
brew install python@3.11
```

Or use the latest version:
```bash
brew install python@3.12
```

### 4. Set Up Project Environment

Navigate to the project directory:
```bash
cd ~/Desktop/LifeStream
```

Create a virtual environment:
```bash
python3 -m venv venv
```

Activate the virtual environment:
```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt. **Important:** Always activate the virtual environment before working on the project.

### 5. Install Python Dependencies

Upgrade pip first:
```bash
pip install --upgrade pip
```

Install project dependencies:
```bash
pip install -r requirements.txt
```

**Note:** This may take several minutes as it downloads large packages like PyTorch and Whisper models.

### 6. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit the `.env` file with your API keys:
```bash
nano .env
```

Or use your preferred editor (VS Code, TextEdit, etc.).

**Required API Keys:**
- `OPENAI_API_KEY`: Get from https://platform.openai.com/api-keys
- `HUGGINGFACE_TOKEN`: Get from https://huggingface.co/settings/tokens

**Optional Configuration:**
- Adjust model sizes if you have limited resources
- Change output/temp directories if needed
- Modify processing parameters

### 7. Verify Installation

Test that everything is set up correctly:

```bash
# Test Python
python3 --version

# Test FFmpeg
ffmpeg -version

# Test Python packages
python3 -c "import torch; import whisper; print('Dependencies OK')"
```

## Project Structure

After setup, your project should look like this:

```
LifeStream/
├── venv/              # Virtual environment (don't commit)
├── .env               # Your API keys (don't commit)
├── output/            # Generated summaries
├── temp/              # Temporary processing files
├── src/               # Source code
├── tests/             # Test files
└── requirements.txt   # Python dependencies
```

## Running the Pipeline

### Basic Usage

Process a video file:
```bash
python src/main.py --input ~/Videos/meeting.mp4 --output summary.md
```

### Advanced Usage

With verbose logging:
```bash
python src/main.py --input ~/Videos/meeting.mp4 --output summary.md --verbose
```

Specify custom output directory:
```bash
python src/main.py --input ~/Videos/meeting.mp4 --output-dir ./my_outputs
```

## Common Issues & Solutions

### Issue: "FFmpeg not found"

**Solution:**
```bash
# Check if FFmpeg is installed
which ffmpeg

# If not found, ensure Homebrew is in PATH
export PATH="/opt/homebrew/bin:$PATH"

# Add to ~/.zshrc to make permanent
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Issue: "Permission denied" errors

**Solution:**
```bash
# Ensure directories have correct permissions
chmod -R 755 temp output

# Or create directories manually
mkdir -p temp output
```

### Issue: Model download fails

**Solutions:**
1. Check internet connection
2. Verify HuggingFace token in `.env`
3. Clear cache and retry:
   ```bash
   rm -rf ~/.cache/huggingface
   rm -rf ~/.cache/torch
   ```

### Issue: Out of memory errors

**Solutions:**
1. Use smaller models (edit `.env`):
   ```
   ASR_MODEL=base  # Instead of large
   ```
2. Process videos in smaller chunks
3. Close other applications to free up RAM
4. Restart your Mac to clear memory

### Issue: Slow processing

**Solutions:**
1. Use smaller models for testing
2. Enable GPU acceleration (if available on Apple Silicon):
   - PyTorch should automatically use Metal on M1/M2 Macs
   - Verify with: `python3 -c "import torch; print(torch.backends.mps.is_available())"`
3. Process shorter video clips for testing

### Issue: "No module named 'X'"

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Performance Optimization

### For Apple Silicon Macs (M1/M2/M3)

1. **Use optimized PyTorch:**
   - PyTorch should automatically detect and use Metal Performance Shaders
   - Verify: `python3 -c "import torch; print(torch.backends.mps.is_available())"`

2. **Whisper Optimization:**
   - Whisper can use Metal on Apple Silicon
   - Consider using smaller models for faster processing

3. **Memory Management:**
   - Monitor memory usage in Activity Monitor
   - Process videos in chunks if memory is limited

### Storage Management

Temporary files can be large. Monitor disk space:
```bash
# Check disk usage
df -h

# Clean up temp files manually
rm -rf temp/*

# Or enable automatic cleanup in settings
```

## Development Workflow

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Make changes to code**

3. **Run tests:**
   ```bash
   pytest tests/
   ```

4. **Test with sample video:**
   ```bash
   python src/main.py --input test_video.mp4 --output test_output.md
   ```

5. **Deactivate when done:**
   ```bash
   deactivate
   ```

## Next Steps

- Read [STAGE1_IMPLEMENTATION_PLAN.md](./STAGE1_IMPLEMENTATION_PLAN.md) for implementation details
- Start with Phase 1: Foundation & Data Models
- Test each feature as you implement it

## Getting Help

If you encounter issues not covered here:

1. Check the main [README.md](./README.md)
2. Review [STAGE1_IMPLEMENTATION_PLAN.md](./STAGE1_IMPLEMENTATION_PLAN.md)
3. Check error logs in the console output
4. Verify all prerequisites are installed correctly

## Notes

- **Virtual Environment:** Always activate `venv` before running the project
- **API Costs:** Be aware of API usage costs, especially for LLM calls
- **Model Caching:** Models are cached in `~/.cache/` - first run will be slower
- **Temp Files:** Large videos create large temp files - ensure sufficient disk space

---

**Last Updated:** 2026-01-09
