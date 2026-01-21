#!/usr/bin/env python3
"""Run the LifeStream API server.

Usage:
    python run_api.py
    python run_api.py --host 0.0.0.0 --port 8000
    python run_api.py --reload  # For development
"""

import argparse
import uvicorn
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LifeStream API server")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    
    args = parser.parse_args()
    
    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
    )
