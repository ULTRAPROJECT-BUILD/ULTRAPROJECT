# imagegen MCP Server

Image generation via Together.ai API. Supports FLUX.1 Schnell (free), FLUX.1 Pro, FLUX.1.1 Pro, and Stable Diffusion XL.

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| TOGETHER_API_KEY | Yes | Together.ai API key. Free tier available at https://api.together.xyz/ |

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Tools

| Tool | Description |
|------|-------------|
| generate_image | Generate an image from a text prompt and save as PNG. Supports custom dimensions, model selection, and step count. |
| list_models | List available image generation models with pricing and recommended settings. |

## Registration

Add to `.mcp.json`:
```json
{
  "imagegen": {
    "type": "stdio",
    "command": "python3",
    "args": ["vault/clients/_platform/mcps/imagegen/server.py"],
    "env": {
      "TOGETHER_API_KEY": "your-api-key-here"
    }
  }
}
```
