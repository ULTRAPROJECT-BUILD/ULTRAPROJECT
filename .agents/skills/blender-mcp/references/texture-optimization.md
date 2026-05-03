# Texture Optimization Pipeline

Target: smallest GLB with acceptable visual quality for web delivery.

---

## Pipeline Overview

```
Blender export (no Draco)
        |
        v
   inspect (gltf-transform)
        |
        v
   resize to 1K max
        |
        v
   WebP compression (q85-90)
        |
        v
   Draco mesh compression (LAST)
        |
        v
   final inspect + validate
```

**Typical size reduction:**

| Stage | Size | Notes |
|-------|------|-------|
| Raw Blender export | ~22 MB | 4K PNG textures, no mesh compression |
| After resize 1024x1024 | ~3.7 MB | 16x GPU memory reduction |
| After WebP q90 | ~3.7 MB | File size drops, GPU memory same |
| After Draco | ~1.0 MB | ~75% mesh data reduction |

---

## Step-by-Step Commands

### Step 0: Install gltf-transform

```bash
npm install -g @gltf-transform/cli
# or use via npx without installing:
npx @gltf-transform/cli --help
```

### Step 1: Inspect Before Optimizing

Always inspect before touching anything. You need a baseline.

```bash
npx @gltf-transform/cli inspect input.glb
```

Example output to read:

```
SCENE     Spot Lighting
 MESH     16 meshes, 12,847 primitives
 SKIN     0 skins
 ANIM     3 animations (45.0s / 1350 frames)
 TEXTURE  8 textures
  image/png  3 textures, 12.4 MB
  image/jpeg 5 textures, 4.2 MB
 GPU EST  ~89.3 MB VRAM
```

Key metrics to note:
- `GPU EST` — estimated VRAM usage. Over 50 MB is heavy for mobile. Over 100 MB will OOM on low-end devices.
- Texture count and format — PNGs are larger, JPEGs are lossy, WebP is smaller with same quality
- Individual texture sizes — find which textures dominate total size

### Step 2: Resize Textures

```bash
# Resize all textures to max 1024x1024
npx @gltf-transform/cli resize input.glb resized.glb --width 1024 --height 1024

# For higher-fidelity desktop targets (still reasonable):
npx @gltf-transform/cli resize input.glb resized.glb --width 2048 --height 2048

# For very lightweight mobile targets:
npx @gltf-transform/cli resize input.glb resized.glb --width 512 --height 512
```

**GPU memory impact per texture at different sizes:**

| Resolution | GPU Memory (RGBA) | Notes |
|------------|-------------------|-------|
| 4096x4096 | ~89 MB | Desktop only, very heavy |
| 2048x2048 | ~22 MB | Acceptable for desktop |
| 1024x1024 | ~5.6 MB | Good web/mobile target |
| 512x512 | ~1.4 MB | Mobile minimum quality |

**With 8 textures at 4K:** ~712 MB VRAM total — crashes most mobile browsers.
**With 8 textures at 1K:** ~45 MB VRAM total — workable on mid-range mobile.

### Step 3: WebP Compression

```bash
# Quality 90 — high fidelity, good for hero assets
npx @gltf-transform/cli webp resized.glb webp.glb --quality 90

# Quality 85 — recommended default (smaller file, imperceptible quality loss)
npx @gltf-transform/cli webp resized.glb webp.glb --quality 85

# Quality 75 — aggressive compression, acceptable for background/prop assets
npx @gltf-transform/cli webp resized.glb webp.glb --quality 75
```

**Quality setting guide:**

| Quality | Use case | File size vs q90 |
|---------|----------|-----------------|
| 90 | Hero characters, close-up assets | 1x (baseline) |
| 85 | Standard assets | ~0.7x |
| 75 | Background props, distant objects | ~0.5x |
| 60 | Thumbnails, preview LODs | ~0.35x |

**Important:** WebP reduces file download size but does NOT reduce GPU memory. The GPU still decompresses to the full bitmap. Only resizing reduces GPU memory.

**Texture type quality recommendations:**

| Texture type | Recommended quality | Reason |
|-------------|---------------------|--------|
| Base color (diffuse) | 85-90 | Color accuracy visible to eye |
| Normal map | 90 | Low-quality normals cause visible banding |
| MetallicRoughness | 85 | Channel precision less perceptible |
| Emissive | 85 | Glow artifacts masked by bloom |
| Occlusion | 80 | Subtle, low-frequency data |

### Step 4: Draco Mesh Compression

```bash
# Default settings (good for most cases)
npx @gltf-transform/cli draco webp.glb final.glb

# Higher compression (smaller file, more decode time)
npx @gltf-transform/cli draco webp.glb final.glb \
  --quantize-position 14 \
  --quantize-normal 10 \
  --quantize-texcoord 12

# Lower compression (faster decode, good for interactive scenes with many objects)
npx @gltf-transform/cli draco webp.glb final.glb \
  --quantize-position 11 \
  --quantize-normal 8 \
  --quantize-texcoord 10
```

**Draco quantization bits guide:**

| Parameter | Default | Range | Trade-off |
|-----------|---------|-------|-----------|
| `--quantize-position` | 14 | 8-16 | Higher = more accurate vertex positions |
| `--quantize-normal` | 10 | 6-12 | Higher = smoother curved surfaces |
| `--quantize-texcoord` | 12 | 8-14 | Higher = less UV seam artifacts |

**WARNING:** Draco is irreversible. Always keep an uncompressed version as source.

**WARNING:** Do NOT apply Draco if you exported with Draco from Blender. Re-encoding corrupts meshes. The pipeline must be: Blender (no Draco) → gltf-transform Draco.

### Step 5: Final Inspect

```bash
npx @gltf-transform/cli inspect final.glb
```

Compare against baseline inspection from Step 1. Verify:
- GPU EST is below target (50 MB for mobile, 200 MB for desktop)
- Texture formats show `image/webp`
- Mesh compression shows `draco`
- Animation count matches original

---

## Complete Pipeline Script

For repeatability, use a shell script:

```bash
#!/bin/bash
# optimize-glb.sh — full optimization pipeline
# Usage: ./optimize-glb.sh input.glb output_dir/

set -e

INPUT="$1"
OUTPUT_DIR="${2:-.}"
BASENAME=$(basename "$INPUT" .glb)

echo "=== Inspecting source: $INPUT ==="
npx @gltf-transform/cli inspect "$INPUT"

echo ""
echo "=== Resizing textures to 1024x1024 ==="
npx @gltf-transform/cli resize "$INPUT" "$OUTPUT_DIR/${BASENAME}_resized.glb" \
  --width 1024 --height 1024

echo ""
echo "=== WebP compression (quality 85) ==="
npx @gltf-transform/cli webp \
  "$OUTPUT_DIR/${BASENAME}_resized.glb" \
  "$OUTPUT_DIR/${BASENAME}_webp.glb" \
  --quality 85

echo ""
echo "=== Draco mesh compression ==="
npx @gltf-transform/cli draco \
  "$OUTPUT_DIR/${BASENAME}_webp.glb" \
  "$OUTPUT_DIR/${BASENAME}_final.glb"

echo ""
echo "=== Final inspection ==="
npx @gltf-transform/cli inspect "$OUTPUT_DIR/${BASENAME}_final.glb"

echo ""
echo "=== Size comparison ==="
echo "Source:  $(du -sh "$INPUT" | cut -f1)"
echo "Final:   $(du -sh "$OUTPUT_DIR/${BASENAME}_final.glb" | cut -f1)"
```

---

## Advanced: Selective Texture Operations

### Resize only specific textures

```bash
# List texture names first
npx @gltf-transform/cli inspect input.glb --format table

# Use Node.js API for selective operations:
node -e "
const { NodeIO } = require('@gltf-transform/core');
const { resize } = require('@gltf-transform/functions');

async function run() {
    const io = new NodeIO();
    const doc = await io.read('input.glb');

    for (const tex of doc.getRoot().listTextures()) {
        const name = tex.getName();
        if (name.includes('background') || name.includes('skybox')) {
            // Skip background textures — they are meant to be large
            continue;
        }
        // Apply resize to all other textures
        const img = tex.getImage();
        if (img) {
            console.log('Resizing:', name);
        }
    }

    await io.write('output.glb', doc);
}

run().catch(console.error);
"
```

### Convert only PNG textures to WebP (preserve existing WebP/JPEG)

```bash
# gltf-transform webp converts all by default
# To be selective, inspect first and decide per texture
npx @gltf-transform/cli inspect input.glb
```

---

## Quality Metrics Reference

Use these metrics to evaluate output quality before shipping:

### File size targets (web delivery)

| Asset type | Raw export | Acceptable final | Excellent final |
|-----------|-----------|-----------------|-----------------|
| Character model + animations | 15-30 MB | < 5 MB | < 2 MB |
| Environment scene | 20-50 MB | < 8 MB | < 4 MB |
| Prop/object | 1-5 MB | < 1 MB | < 300 KB |
| Icon/small asset | < 1 MB | < 100 KB | < 50 KB |

### GPU VRAM targets

| Platform | Target VRAM per scene | Notes |
|----------|----------------------|-------|
| High-end desktop | < 500 MB | RTX 3080+, integrated scenes |
| Mid desktop / console | < 200 MB | RTX 2060, PS5 |
| High-end mobile | < 100 MB | iPhone 14+, Snapdragon 8 Gen 2 |
| Mid-range mobile | < 50 MB | Snapdragon 778G, Helio G99 |
| Low-end mobile | < 20 MB | Budget Android |

### Visual quality checklist

- Normal maps: no visible faceting at expected viewing distance
- Base color: no visible compression artifacts on flat color surfaces
- Roughness: no banding on smooth gradient surfaces
- Metalness: specular highlights look physically correct
- Animations: no vertex snapping (visible with low `--quantize-position`)

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Used `gltf-transform optimize` | Mesh geometry destroyed | Always use individual steps: resize → webp → draco |
| Applied Draco in Blender then again in gltf-transform | Corrupted/missing mesh | Export from Blender with `export_draco_mesh_compression_enable=False` |
| Skipped resize, only ran WebP | Still high GPU VRAM | Run resize first — WebP doesn't reduce VRAM |
| Quantize-position too low | Vertex positions snap/jump | Use 12+ bits for position quantization |
| Optimized without backup | Cannot recover quality | Always keep uncompressed intermediate files |
| Ran optimization on already-Draco GLB | No further compression, possible errors | Start from the raw Blender export |
