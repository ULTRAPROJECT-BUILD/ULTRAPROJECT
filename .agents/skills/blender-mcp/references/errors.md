# Blender MCP Error Reference

## MCP Server Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Export timeout | GLTF export exceeds MCP timeout (~15-30s) | Use headless CLI: `blender --background file.blend --python-expr "..."` |
| Connection refused on port 9876 | MCP addon not running | Enable Blender MCP addon in Preferences → Add-ons, restart Blender |
| Socket timeout | Blender is busy (rendering, heavy computation) | Wait for current operation to finish, retry |
| Script execution timeout | Python script too slow | Split into smaller scripts, reduce iteration count |

## GLTF Export Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Corrupt mesh after Draco re-encode | Applied Draco twice (export + gltf-transform) | Export WITHOUT Draco, apply Draco as final gltf-transform step |
| Mesh destroyed by `optimize` | `gltf-transform optimize` includes `simplify` | Use individual steps: `resize` → `webp` → `draco` |
| Missing textures in GLB | Broken texture paths (e.g., `textures/textures/` double nesting) | Check `File → External Data → Report Missing Files` in Blender |
| Materials look flat | Color Ramp remapping lost on export | Apply manual roughness/metalness values at runtime |
| Procedural roughness missing | Noise Texture nodes don't export | Bake to texture in Blender, or use runtime shader patch |
| Giant file size | Array modifiers baked on export | Set `export_apply=False`, replicate arrays at runtime |

## Blender Python API Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `RuntimeError: Operator bpy.ops.export_scene.gltf.poll() failed` | No active scene or context override needed | Run in correct context or use `--background` mode |
| `AttributeError: 'NoneType' has no attribute 'nodes'` | Material has `use_nodes = False` | Check `mat.use_nodes` before accessing `mat.node_tree.nodes` |
| `KeyError: 'Principled BSDF'` | Material uses non-standard shader | Iterate `node_tree.nodes` and filter by `node.type == 'BSDF_PRINCIPLED'` |
| `RecursionError` in hierarchy traversal | Deep nesting hits Python limit | Use iterative (stack-based) traversal instead of recursion |
| `bpy.context.scene` is None in background mode | Context not fully initialized | Use `bpy.data.scenes[0]` or `bpy.context.window.scene` |

## Texture Path Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Textures not packed in GLB | External file references with relative paths | `File → External Data → Pack Resources` before export |
| Double-nested path (`textures/textures/`) | Incorrect relative path in Blender | Fix path in Image Editor or via `bpy.data.images["name"].filepath` |
| 4K texture causing mobile GPU OOM | Texture too large for mobile VRAM | Resize to 1024x1024 via gltf-transform |

## GLTF Name Mapping Gotchas

| Issue | Example | Notes |
|-------|---------|-------|
| Spaces → underscores | `RINGS ball L` → `RINGS_ball_L` | Always check GLB names, not Blender names |
| Dots removed | `Sphere.003` → `Sphere003` | Dot-number suffixes collapse |
| Trailing spaces → underscore | `RINGS S ` → `RINGS_S_` | Easy to miss in Blender UI |
| Duplicate names | Two objects named `Cube` | GLTF appends `_1`, `_2` — unpredictable |

## Material Export Survival Matrix

| Blender Feature | Exports to GLTF? | Notes |
|----------------|-------------------|-------|
| Flat roughness/metallic values | Yes | Direct mapping |
| Image textures (baseColor, normal) | Yes | Packed or referenced |
| Image roughness texture | Partially | Texture exports, Color Ramp remapping lost |
| Procedural Noise Texture | No | Must bake or patch at runtime |
| Color Ramp value remapping | No | Range compression lost |
| Bump from Noise node | No | Bake to normal map |
| Baked normal maps | Yes | Standard GLTF feature |
| Alpha from texture | Yes | Via alphaMode |
| Emission | Yes | Via emissiveFactor / emissiveTexture |
| Separate metallic + roughness channels | Yes | Combined into metallicRoughness texture |
