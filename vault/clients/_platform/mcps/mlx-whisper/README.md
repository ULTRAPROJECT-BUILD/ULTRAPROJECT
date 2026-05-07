# mlx-whisper MCP Server

Local audio transcription on Apple Silicon using MLX Whisper. Runs entirely on-device with no API keys or cloud services. First transcription downloads the Whisper model (~1.6GB) automatically.

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.12+
- ~2GB disk space for model download

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| MLX_WHISPER_MODEL | No | HuggingFace model path (default: mlx-community/whisper-large-v3-turbo) |

## Install Dependencies

```bash
pip install -r requirements.txt
```

Note: `mlx-whisper` installs `mlx` and related Apple Silicon ML dependencies automatically.

## Tools

| Tool | Description |
|------|-------------|
| transcribe_audio | Transcribe an audio file to text (file path -> JSON with text) |
| transcribe_with_timestamps | Transcribe with segment-level timestamps |
| list_supported_formats | List supported audio formats |

## Supported Audio Formats

MP3, WAV, M4A, FLAC, OGG, WebM, MP4

## Registration

Add to `.mcp.json`:
```json
{
  "mlx-whisper": {
    "type": "stdio",
    "command": "python3.12",
    "args": ["vault/clients/_platform/mcps/mlx-whisper/server.py"],
    "env": {}
  }
}
```
