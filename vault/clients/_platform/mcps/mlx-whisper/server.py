"""
mlx-whisper MCP Server
Local audio transcription on Apple Silicon using MLX Whisper.
No API keys needed — runs entirely on-device.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mlx-whisper")


# --- Configuration ---

MODEL_PATH = os.environ.get(
    "MLX_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo"
)

SUPPORTED_FORMATS = {
    "mp3": "MPEG Audio Layer 3",
    "wav": "Waveform Audio",
    "m4a": "MPEG-4 Audio",
    "flac": "Free Lossless Audio Codec",
    "ogg": "Ogg Vorbis",
    "webm": "WebM Audio",
    "mp4": "MPEG-4 (audio track)",
}


# --- Lazy import for mlx_whisper ---

_mlx_whisper = None


def _get_mlx_whisper():
    """Lazy-load mlx_whisper to avoid import errors at startup."""
    global _mlx_whisper
    if _mlx_whisper is None:
        try:
            import mlx_whisper
            _mlx_whisper = mlx_whisper
        except ImportError:
            raise RuntimeError(
                "mlx-whisper is not installed. "
                "Install with: pip install mlx-whisper"
            )
    return _mlx_whisper


# --- Tools ---


@mcp.tool()
def transcribe_audio(
    file_path: str,
    language: Optional[str] = "en",
    task: str = "transcribe",
) -> str:
    """Transcribe an audio file to text using MLX Whisper (local, on-device).

    Args:
        file_path: Absolute path to the audio file (MP3, WAV, M4A, FLAC, OGG, WebM, MP4)
        language: Language code (e.g., "en", "fr", "es", "de", "ja"). Default "en".
                  Use None or "" for auto-detection.
        task: "transcribe" (keep original language) or "translate" (translate to English)

    Returns:
        JSON with transcription text, detected language, and file info
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        suffix = path.suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_FORMATS:
            return json.dumps({
                "error": f"Unsupported format: .{suffix}",
                "supported": list(SUPPORTED_FORMATS.keys()),
            })

        whisper = _get_mlx_whisper()

        lang = language if language else None
        result = whisper.transcribe(
            str(path),
            path_or_hf_repo=MODEL_PATH,
            language=lang,
            task=task,
        )

        return json.dumps({
            "text": result.get("text", "").strip(),
            "language": result.get("language", language or "auto"),
            "file": str(path),
            "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            "model": MODEL_PATH,
            "task": task,
        })

    except Exception as e:
        return json.dumps({"error": f"Transcription failed: {str(e)}"})


@mcp.tool()
def transcribe_with_timestamps(
    file_path: str,
    language: Optional[str] = "en",
    task: str = "transcribe",
) -> str:
    """Transcribe audio with segment-level timestamps.

    Args:
        file_path: Absolute path to the audio file
        language: Language code (e.g., "en", "fr"). Default "en". Use None for auto-detect.
        task: "transcribe" or "translate" (to English)

    Returns:
        JSON with timestamped segments and full text
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        suffix = path.suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_FORMATS:
            return json.dumps({
                "error": f"Unsupported format: .{suffix}",
                "supported": list(SUPPORTED_FORMATS.keys()),
            })

        whisper = _get_mlx_whisper()

        lang = language if language else None
        result = whisper.transcribe(
            str(path),
            path_or_hf_repo=MODEL_PATH,
            language=lang,
            task=task,
        )

        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg.get("start", 0), 2),
                "end": round(seg.get("end", 0), 2),
                "text": seg.get("text", "").strip(),
            })

        full_text = result.get("text", "").strip()

        return json.dumps({
            "text": full_text,
            "segments": segments,
            "segment_count": len(segments),
            "language": result.get("language", language or "auto"),
            "file": str(path),
            "model": MODEL_PATH,
            "task": task,
        })

    except Exception as e:
        return json.dumps({"error": f"Transcription failed: {str(e)}"})


@mcp.tool()
def list_supported_formats() -> str:
    """List audio formats supported by the MLX Whisper transcription server.

    Returns:
        JSON with supported file extensions and descriptions
    """
    return json.dumps({
        "formats": SUPPORTED_FORMATS,
        "model": MODEL_PATH,
        "note": "First transcription will download the model (~1.6GB). Requires Apple Silicon Mac.",
    })


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
