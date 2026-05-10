---
type: skill
name: build-remotion-video
description: "Creates short-form vertical video (TikTok/Reels) using Remotion — scaffolds project, writes React composition, renders MP4"
inputs:
  - client (required — client slug)
  - project (required — project slug for deliverable path)
  - creative_brief (optional — path to creative brief snapshot)
  - audio_path (optional — path to background music file)
  - duration_seconds (optional — video length, default: 30)
---

# Build Remotion Video

You are creating a short-form vertical video (TikTok, Reels, Shorts format) using Remotion, a React-based programmatic video framework. The output is a rendered MP4 file ready for social media upload or client delivery.

**Prerequisites:** FFmpeg, Node.js, and npx must be available on the system. Verify before starting:

```bash
ffmpeg -version && node --version && npx --version
```

If any prerequisite is missing, stop and report the gap. Do not attempt to install system-level dependencies.

## Process

### Step 1: Set Up Project Directory

1. Create a working directory for the video:
   ```
   vault/clients/{client}/deliverables/{project}/video/
   ```

2. Initialize a Remotion project inside the working directory:
   ```bash
   cd vault/clients/{client}/deliverables/{project}/video/
   npx create-video@latest --template blank --no-git
   ```
   If `create-video` fails or hangs, scaffold manually:
   - Create `package.json` with `remotion`, `@remotion/cli`, `@remotion/bundler`, `react`, `react-dom` as dependencies.
   - Create `src/index.ts` with `registerRoot` pointing to `Root`.
   - Create `src/Root.tsx` with a placeholder composition.
   - Create `tsconfig.json` with standard React + TypeScript settings.

3. Install dependencies:
   ```bash
   npm install
   ```

4. Verify the scaffold works:
   ```bash
   npx remotion compositions src/index.ts
   ```
   This should list at least one composition without errors.

### Step 2: Read Creative Brief

1. If `creative_brief` path is provided, read it directly.
2. If not provided, search for a creative brief in:
   - `vault/clients/{client}/snapshots/` — look for files with `creative` and `brief` in the name or frontmatter tags.
   - The project file at `vault/clients/{client}/projects/{project}.md` — check for linked briefs.
3. Extract from the brief:
   - **Topic** — what the video is about
   - **Tone** — energetic, calm, professional, playful, etc.
   - **Visual style** — minimalist, bold, cinematic, retro, etc.
   - **Color palette** — primary, secondary, accent hex codes
   - **Text content** — headlines, taglines, body copy for each scene
   - **Scene breakdown** — how many scenes, what each shows, timing
   - **CTA** — what the viewer should do at the end
4. If no creative brief exists anywhere, log this gap in the ticket work log and proceed with sensible defaults:
   - 5 scenes of equal length
   - Clean, modern visual style
   - Brand colors from `vault/clients/{client}/config.md` if available
   - Generic CTA: "Learn More" with client domain/contact

### Step 3: Write the Composition

1. Create `src/Root.tsx` — the root component that registers the composition:

   ```tsx
   import { Composition } from "remotion";
   import { Main } from "./Main";

   export const RemotionRoot: React.FC = () => {
     return (
       <Composition
         id="Main"
         component={Main}
         durationInFrames={durationInFrames}
         fps={30}
         width={1080}
         height={1920}
       />
     );
   };
   ```

   - **Resolution:** 1080x1920 (9:16 vertical, standard for TikTok/Reels/Shorts)
   - **FPS:** 30
   - **Duration:** `duration_seconds * 30` frames (default: 900 frames = 30 seconds)

2. Create `src/Main.tsx` — the main composition that arranges scenes using `<Sequence>`:

   ```tsx
   import { AbsoluteFill, Sequence } from "remotion";
   import { SceneOne } from "./scenes/SceneOne";
   import { SceneTwo } from "./scenes/SceneTwo";
   // ... additional scenes

   export const Main: React.FC = () => {
     const sceneDuration = 180; // frames per scene (6 seconds at 30fps)
     return (
       <AbsoluteFill>
         <Sequence from={0} durationInFrames={sceneDuration}>
           <SceneOne />
         </Sequence>
         <Sequence from={sceneDuration} durationInFrames={sceneDuration}>
           <SceneTwo />
         </Sequence>
         {/* ... additional scenes */}
       </AbsoluteFill>
     );
   };
   ```

3. Create individual scene components in `src/scenes/`. Each scene should include:

   **Animated text overlays** using `useCurrentFrame()` and `interpolate()`:
   ```tsx
   const frame = useCurrentFrame();
   const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
   const translateY = interpolate(frame, [0, 20], [40, 0], { extrapolateRight: "clamp" });
   ```

   **Background visuals** — CSS gradients, geometric shapes, or images:
   ```tsx
   <AbsoluteFill style={{ background: "linear-gradient(135deg, #1a1a2e, #16213e)" }}>
   ```

   **Scene transitions** — fade, slide, or scale between scenes:
   ```tsx
   const fadeOut = interpolate(frame, [durationInFrames - 15, durationInFrames], [1, 0], {
     extrapolateLeft: "clamp",
     extrapolateRight: "clamp",
   });
   ```

   **Natural motion** using `spring()`:
   ```tsx
   import { spring, useVideoConfig } from "remotion";
   const { fps } = useVideoConfig();
   const scale = spring({ frame, fps, config: { damping: 200 } });
   ```

   **Call-to-action** in the final scene — make it bold, clear, and visually distinct.

4. Design principles for TikTok-style video:
   - **Large text** — minimum 60px for headlines, readable on mobile
   - **High contrast** — text must pop against backgrounds
   - **Fast pacing** — scenes should change every 3-6 seconds
   - **Vertical framing** — all content centered in the middle 80% of the frame to avoid platform UI overlap
   - **Safe zones** — keep critical content away from top 15% (username) and bottom 20% (description/buttons)

### Step 4: Add Audio

1. **Background music** — if `audio_path` is provided:
   ```tsx
   import { Audio } from "remotion";

   <Audio src={staticFile("background.mp3")} volume={0.3} />
   ```
   Copy the audio file to the project's `public/` directory so `staticFile()` can reference it.

2. **Text-to-speech voiceover** — if the brief calls for narration:
   ```bash
   # Generate voiceover using macOS say command
   say -o voiceover.aiff "Your narration text here"

   # Convert to mp3 with FFmpeg
   ffmpeg -i voiceover.aiff -codec:a libmp3lame -qscale:a 2 public/voiceover.mp3
   ```

   Add the voiceover as an `<Audio>` component, timing it with `<Sequence>` to sync with visual scenes:
   ```tsx
   <Sequence from={0} durationInFrames={180}>
     <Audio src={staticFile("voiceover-scene1.mp3")} />
   </Sequence>
   ```

3. **No audio** — if neither music nor voiceover is needed, skip this step. The video will be silent (many TikTok videos rely on the platform's music overlay feature).

### Step 5: Preview and Iterate

1. **In headed environments**, run the Remotion preview server:
   ```bash
   npx remotion preview src/index.ts
   ```
   This opens a browser-based preview at `http://localhost:3000`.

2. **In headless environments** (typical for this platform), generate still frames for visual verification:
   ```bash
   # Capture key frames — one from each scene
   npx remotion still src/index.ts Main --frame=0 out/still-frame-000.png
   npx remotion still src/index.ts Main --frame=180 out/still-frame-180.png
   npx remotion still src/index.ts Main --frame=360 out/still-frame-360.png
   npx remotion still src/index.ts Main --frame=540 out/still-frame-540.png
   npx remotion still src/index.ts Main --frame=720 out/still-frame-720.png
   ```

3. Inspect the still frames visually:
   - Are colors correct and matching the brief?
   - Is text readable and well-positioned?
   - Are transitions landing on the right frames?
   - Is the safe zone respected (no text in top 15% or bottom 20%)?

4. If issues are found, fix the composition code and regenerate stills. Do not proceed to render until stills look correct.

### Step 6: Render to MP4

1. Render the final video:
   ```bash
   npx remotion render src/index.ts Main out/video.mp4 --codec h264
   ```

2. Verify the output:
   ```bash
   # Check file exists and get metadata
   ffprobe -v quiet -print_format json -show_format -show_streams out/video.mp4
   ```
   Confirm:
   - File exists and is non-zero size
   - Duration is approximately `duration_seconds` (default: ~30s)
   - Resolution is 1080x1920
   - Codec is H.264

3. If audio was prepared separately and not embedded via Remotion's `<Audio>` component, mux it with FFmpeg:
   ```bash
   ffmpeg -i out/video.mp4 -i audio.mp3 -c:v copy -c:a aac -shortest out/video-with-audio.mp4
   mv out/video-with-audio.mp4 out/video.mp4
   ```

### Step 7: Post-Process (Optional)

1. **Optimize for TikTok upload** — re-encode with settings optimized for social media:
   ```bash
   ffmpeg -i out/video.mp4 \
     -c:v libx264 -preset slow -crf 18 \
     -c:a aac -b:a 128k \
     -movflags +faststart \
     out/final.mp4
   ```
   The `-movflags +faststart` flag moves the moov atom to the beginning of the file for faster streaming playback.

2. **Verify file size** — TikTok allows up to 287MB, but for email delivery keep it under 25MB:
   ```bash
   ls -lh out/final.mp4
   ```
   If the file is too large:
   - Increase CRF (e.g., `-crf 23`) to reduce quality slightly
   - Reduce resolution to 720x1280 if needed
   - Shorten duration if appropriate

3. **Copy the final deliverable** to the project deliverables directory:
   ```bash
   cp out/final.mp4 vault/clients/{client}/deliverables/{project}/video-final.mp4
   ```

## Output

Return:
- **Video path:** absolute path to the rendered MP4 file
- **Duration:** confirmed duration in seconds
- **Resolution:** confirmed width x height
- **File size:** in MB
- **Audio:** whether background music and/or voiceover were included
- **Still frames:** paths to preview stills for visual verification
- **Brief compliance:** whether the video matches the creative brief's direction (colors, tone, content)

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `npx create-video` hangs or fails | Network issue or npm registry problem | Scaffold the project manually (see Step 1 fallback) |
| `npm install` fails | Dependency conflicts or Node version mismatch | Check Node version (>=18 required for Remotion 4.x), clear npm cache, retry |
| Composition not found | `registerRoot` not wired correctly | Verify `src/index.ts` imports and calls `registerRoot(RemotionRoot)` |
| Render crashes with memory error | Video too long or too many concurrent renders | Reduce `--concurrency` flag, render in segments, increase Node memory with `--max-old-space-size=8192` |
| Black frames in output | Component returns null or transparent background | Add explicit `backgroundColor` to `AbsoluteFill`, verify scene timing with `<Sequence>` `from` and `durationInFrames` |
| Audio out of sync | Mismatched frame timing between audio and visual sequences | Align `<Audio>` components with their parent `<Sequence>` timing, verify audio file duration matches expected scene length |
| FFmpeg not found | FFmpeg not installed or not in PATH | Verify with `ffmpeg -version`; install with the host package manager, e.g. `brew install ffmpeg`, `winget install Gyan.FFmpeg`, or `sudo apt install ffmpeg` |
| Render produces wrong resolution | Composition dimensions set incorrectly | Verify `width={1080} height={1920}` in the `<Composition>` component |
| File too large for email | High bitrate or long duration | Re-encode with higher CRF value (23-28), or reduce resolution |
| TypeScript compilation errors | Missing type definitions or syntax errors | Run `npx tsc --noEmit` to check types before rendering, install `@types/react` if missing |

## When to Use

- When a project ticket calls for a short-form video (TikTok, Reels, YouTube Shorts)
- When the creative brief specifies animated/motion content for social media
- When a client needs a promotional video and no stock footage or external video editing tool is available
- When building marketing content for the platform itself (self-marketing projects)

## Principles

- **Brief first.** Never start composing video without a creative brief. The brief defines colors, tone, content, and quality bar. Without it, the output will be generic.
- **Stills before render.** Always verify key frames with `remotion still` before committing to a full render. Rendering takes time — catch problems early.
- **Mobile-first framing.** Everything in the video must be readable on a phone screen. Oversized text is better than undersized.
- **Respect safe zones.** TikTok overlays UI on the top and bottom of videos. Keep critical content in the middle 70% of the frame vertically.
- **Less is more.** 3-5 punchy scenes beat 10 cluttered ones. Each scene should communicate one idea.

## See Also

- [[creative-brief]]
- [[self-review]]
- [[source-capability]]
