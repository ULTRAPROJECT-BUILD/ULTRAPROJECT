"""
Image Generation MCP Server — Together.ai FLUX.1

Generates images from text prompts using the Together.ai inference API.
Supports multiple models including FLUX.1 Schnell (free tier), FLUX.1 Pro,
FLUX.1.1 Pro, and Stable Diffusion XL.

Requires TOGETHER_API_KEY environment variable.
Free tier: FLUX.1 Schnell is free. Other models require a paid plan.
"""

import base64
import json
import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOGETHER_API_URL = "https://api.together.xyz/v1/images/generations"
API_KEY = os.environ.get("TOGETHER_API_KEY", "")
REQUEST_TIMEOUT = 60  # image generation can take a while

# Known Together.ai image generation models
KNOWN_MODELS = [
    {
        "id": "black-forest-labs/FLUX.1-schnell",
        "name": "FLUX.1 Schnell",
        "description": "Fast image generation model. Free tier available.",
        "pricing": "free",
        "max_steps": 4,
        "default_steps": 4,
    },
    {
        "id": "black-forest-labs/FLUX.1-pro",
        "name": "FLUX.1 Pro",
        "description": "High-quality image generation model with better prompt adherence.",
        "pricing": "paid",
        "max_steps": 50,
        "default_steps": 28,
    },
    {
        "id": "black-forest-labs/FLUX.1.1-pro",
        "name": "FLUX.1.1 Pro",
        "description": "Latest FLUX pro model with improved quality and speed.",
        "pricing": "paid",
        "max_steps": 50,
        "default_steps": 28,
    },
    {
        "id": "stabilityai/stable-diffusion-xl-base-1.0",
        "name": "Stable Diffusion XL",
        "description": "Stability AI's SDXL base model. Good general-purpose image generation.",
        "pricing": "paid",
        "max_steps": 50,
        "default_steps": 30,
    },
]

VALID_MODEL_IDS = {m["id"] for m in KNOWN_MODELS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_headers() -> dict[str, str]:
    """Build authorization headers for Together.ai API requests."""
    if not API_KEY:
        raise EnvironmentError(
            "TOGETHER_API_KEY environment variable is not set. "
            "Get a free key at https://api.together.xyz/"
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _validate_dimensions(width: int, height: int) -> tuple[int, int]:
    """Validate and clamp image dimensions to API-supported ranges."""
    # Together.ai supports dimensions in multiples of 64, from 256 to 1440
    width = max(256, min(1440, width))
    height = max(256, min(1440, height))
    # Round to nearest multiple of 64
    width = round(width / 64) * 64
    height = round(height / 64) * 64
    return width, height


def _save_image_from_base64(b64_data: str, output_path: str) -> str:
    """Decode base64 image data and save to file. Returns the absolute path."""
    # Ensure parent directory exists
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent_dir, exist_ok=True)

    # Ensure .png extension
    if not output_path.lower().endswith(".png"):
        output_path = output_path + ".png"

    abs_path = os.path.abspath(output_path)
    image_bytes = base64.b64decode(b64_data)

    with open(abs_path, "wb") as f:
        f.write(image_bytes)

    return abs_path


def _save_image_from_url(url: str, output_path: str) -> str:
    """Download image from URL and save to file. Returns the absolute path."""
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent_dir, exist_ok=True)

    if not output_path.lower().endswith(".png"):
        output_path = output_path + ".png"

    abs_path = os.path.abspath(output_path)

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    with open(abs_path, "wb") as f:
        f.write(response.content)

    return abs_path


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("imagegen")


@mcp.tool()
def generate_image(
    prompt: str,
    output_path: str,
    width: int = 1024,
    height: int = 1024,
    model: str = "black-forest-labs/FLUX.1-schnell",
    steps: int = 4,
    n: int = 1,
) -> str:
    """Generate an image from a text prompt using Together.ai and save it as PNG.

    Uses the Together.ai inference API with FLUX.1 models. The default model
    (FLUX.1 Schnell) is free to use. Generated images are saved to the
    specified output path.

    Args:
        prompt: Text description of the image to generate. Be specific and
                descriptive for best results.
        output_path: File path where the generated image will be saved.
                     A .png extension is added if not present. Parent
                     directories are created automatically.
        width: Image width in pixels (256-1440, rounded to nearest 64).
               Default: 1024.
        height: Image height in pixels (256-1440, rounded to nearest 64).
                Default: 1024.
        model: Together.ai model ID. Default: "black-forest-labs/FLUX.1-schnell"
               (free). Use list_models() to see all available models.
        steps: Number of inference steps (1-50). More steps = higher quality
               but slower. Default: 4 (optimal for FLUX.1 Schnell).
        n: Number of images to generate (1-4). Default: 1. When n > 1,
           images are saved with _1, _2, etc. suffixes.

    Returns:
        JSON with file path(s), model used, dimensions, and generation metadata.
    """
    # Validate inputs
    prompt = prompt.strip()
    if not prompt:
        return json.dumps({"error": "Prompt is required. Describe the image you want."})

    if not output_path.strip():
        return json.dumps({"error": "output_path is required. Specify where to save the image."})

    # Validate model
    if model not in VALID_MODEL_IDS:
        return json.dumps({
            "error": f"Unknown model: {model}",
            "valid_models": list(VALID_MODEL_IDS),
            "hint": "Use list_models() to see available models with details.",
        })

    # Validate and clamp dimensions
    width, height = _validate_dimensions(width, height)

    # Clamp steps
    steps = max(1, min(50, steps))

    # Clamp n
    n = max(1, min(4, n))

    # Build API request
    payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "n": n,
        "response_format": "b64_json",
    }

    try:
        headers = _get_headers()

        response = requests.post(
            TOGETHER_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        # Handle API errors
        if response.status_code == 401:
            return json.dumps({
                "error": "Authentication failed. Check that TOGETHER_API_KEY is valid.",
                "hint": "Get a free key at https://api.together.xyz/",
            })

        if response.status_code == 429:
            return json.dumps({
                "error": "Rate limit exceeded. Wait a moment and try again.",
                "status_code": 429,
            })

        if response.status_code == 422:
            error_detail = response.json() if response.text else {}
            return json.dumps({
                "error": "Invalid request parameters.",
                "detail": error_detail,
                "hint": "Check model name, dimensions, and steps values.",
            })

        if response.status_code != 200:
            error_text = response.text[:500] if response.text else "No error details"
            return json.dumps({
                "error": f"Together.ai API returned HTTP {response.status_code}",
                "detail": error_text,
            })

        data = response.json()

        # Extract and save images
        saved_files = []
        images = data.get("data", [])

        for idx, image_data in enumerate(images):
            # Determine save path for this image
            if n == 1:
                save_path = output_path
            else:
                base, ext = os.path.splitext(output_path)
                if not ext:
                    ext = ".png"
                save_path = f"{base}_{idx + 1}{ext}"

            # Together.ai returns either b64_json or url
            b64 = image_data.get("b64_json")
            url = image_data.get("url")

            if b64:
                abs_path = _save_image_from_base64(b64, save_path)
            elif url:
                abs_path = _save_image_from_url(url, save_path)
            else:
                return json.dumps({
                    "error": "API response contained no image data (no b64_json or url).",
                    "raw_keys": list(image_data.keys()),
                })

            file_size_kb = round(os.path.getsize(abs_path) / 1024, 1)
            saved_files.append({
                "path": abs_path,
                "size_kb": file_size_kb,
            })

        result = {
            "status": "success",
            "prompt": prompt,
            "model": model,
            "width": width,
            "height": height,
            "steps": steps,
            "images_generated": len(saved_files),
            "files": saved_files,
        }

        # Include timing if available
        if "created" in data:
            result["api_created_timestamp"] = data["created"]

        return json.dumps(result, indent=2)

    except EnvironmentError as e:
        return json.dumps({"error": str(e)})
    except requests.exceptions.Timeout:
        return json.dumps({
            "error": f"Request timed out after {REQUEST_TIMEOUT}s. "
                     "Image generation can be slow — try fewer steps or smaller dimensions.",
        })
    except requests.exceptions.ConnectionError:
        return json.dumps({
            "error": "Could not connect to Together.ai API. Check network connectivity.",
        })
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {e}"})


@mcp.tool()
def list_models() -> str:
    """List available image generation models on Together.ai.

    Returns a curated list of known image generation models with their
    IDs, descriptions, pricing tier, and recommended settings. Use the
    model ID with generate_image().

    Returns:
        JSON with available models, their capabilities, and pricing info.
    """
    result = {
        "models": KNOWN_MODELS,
        "total": len(KNOWN_MODELS),
        "default_model": "black-forest-labs/FLUX.1-schnell",
        "free_models": [m["id"] for m in KNOWN_MODELS if m["pricing"] == "free"],
        "note": "FLUX.1 Schnell is free and recommended for most use cases. "
                "Pro models require a paid Together.ai plan.",
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
