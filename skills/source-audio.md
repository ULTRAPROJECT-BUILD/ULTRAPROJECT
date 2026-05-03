---
type: skill
name: source-audio
description: "Finds and downloads royalty-free background music for video projects from free libraries"
inputs:
  - mood (required — e.g. "upbeat", "chill", "dramatic")
  - duration_seconds (required — minimum track length needed)
  - client (optional — client slug for file placement)
  - project (optional — project slug for file placement)
  - genre (optional — e.g. "electronic", "acoustic", "hip-hop")
---

# Source Audio

You are sourcing royalty-free background music for a video project. Your job is to find a track that matches the mood and duration requirements, download it, prepare it for video use, and document the source for legal compliance.

## Process

### Step 1: Determine Audio Requirements

1. Read the creative brief or ticket to understand the audio needs.
2. Identify:
   - **Mood** — the emotional tone the music should convey. Common moods for TikTok and short-form video: upbeat, energetic, chill, dramatic, funny, inspirational.
   - **Genre** — if specified (electronic, acoustic, hip-hop, cinematic, lo-fi, etc.). If not specified, infer from the mood and project context.
   - **Tempo** — fast-paced for energetic content, slow for emotional/dramatic, mid-tempo for chill or corporate.
   - **Duration** — the target duration should match or exceed the video length. 30 seconds is typical for TikTok/Reels. Always confirm the video duration from the ticket or project file.
3. If requirements are ambiguous, check the creative brief snapshot for visual direction cues — the music should complement the visual tone.

### Step 2: Search Free Audio Libraries

Search in this priority order. All sources below offer royalty-free, no-attribution-required options:

#### Source 1: Pixabay Music (preferred)

- URL: https://pixabay.com/music/
- Completely free. No attribution required. Safe for commercial use.
- Search by mood and genre keywords (e.g., "upbeat electronic", "chill acoustic").
- Use the Pixabay API or web search to find tracks.
- Download directly as MP3.
- Filter results by duration to match the `duration_seconds` requirement.

#### Source 2: Free Music Archive

- URL: https://freemusicarchive.org/
- Creative Commons licensed tracks.
- **Filter by license:** prefer CC0 (public domain, no attribution). CC-BY is acceptable if attribution can be included in the deliverable documentation.
- Avoid CC-NC (non-commercial) or CC-ND (no-derivatives) licenses unless the use case is confirmed non-commercial and no edits are needed.

#### Source 3: Generated Audio (fallback)

If no suitable track is found in the libraries above, generate simple audio using FFmpeg:

```bash
# Generate a simple tone
ffmpeg -f lavfi -i "sine=frequency=440:duration=30" tone.wav

# Generate a beat by layering tones at different frequencies
ffmpeg -f lavfi -i "sine=frequency=220:duration=30" -f lavfi -i "sine=frequency=330:duration=30" -filter_complex amerge=inputs=2 beat.wav
```

This is a last resort. Generated audio is functional but not polished — flag it in the work log so it can be replaced later if a better track is found.

### Step 3: Download the Track

1. Determine the output directory:
   - If `client` and `project` are provided: `vault/clients/{client}/deliverables/{project}/audio/`
   - If only `client` is provided: `vault/clients/{client}/deliverables/audio/`
   - If neither is provided: download to a temporary working directory and note the path in the output.
2. Create the directory if it does not exist: `mkdir -p {output_dir}`
3. Download the selected audio file to the output directory.
4. Verify the file is valid:
   ```bash
   ffprobe {file}
   ```
   The output should show an audio stream (e.g., `Stream #0:0: Audio: mp3`). If ffprobe fails or shows no audio stream, the file is corrupt — re-download or try another track.
5. Verify duration is sufficient:
   ```bash
   ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {file}
   ```
   The reported duration must be greater than or equal to `duration_seconds`. If it is too short, find a longer track.

### Step 4: Format for Video Use

Prepare the audio file so it is ready to drop into a video project without further conversion:

1. **Convert to standard format** (if the source file is not already MP3 at standard settings):
   ```bash
   ffmpeg -i input.mp3 -ar 44100 -ac 2 -b:a 128k output.mp3
   ```
   Target: 44.1 kHz sample rate, stereo, 128 kbps bitrate.

2. **Trim to match video duration** (if the track is longer than needed):
   ```bash
   ffmpeg -i input.mp3 -t {duration_seconds} -c copy trimmed.mp3
   ```
   Use `-c copy` for speed when no re-encoding is needed.

3. **Normalize volume** (to prevent audio from being too quiet or clipping):
   ```bash
   ffmpeg -i input.mp3 -filter:a loudnorm output.mp3
   ```
   The `loudnorm` filter brings audio to broadcast-standard loudness (-23 LUFS). For social media content where louder is typical, consider targeting -14 LUFS:
   ```bash
   ffmpeg -i input.mp3 -filter:a "loudnorm=I=-14:TP=-1.5:LRA=11" output.mp3
   ```

4. Name the final file clearly: `{project}-bg-music.mp3` or `{mood}-{duration}s.mp3`.

### Step 5: Document the Source

Record the following in the ticket's work log entry. This is required for legal compliance even with royalty-free tracks:

- **Track name:** the title of the track as listed on the source site
- **Source URL:** direct link to the track on the source library
- **License type:** CC0, Pixabay License, CC-BY, or "generated"
- **Artist/creator:** if known
- **Duration:** of the downloaded file in seconds
- **File path:** where the final audio file was saved
- **Attribution required:** yes/no — if yes, note exactly what attribution text is needed

Example work log entry:
```
- sourced background music: "Summer Vibes" from Pixabay Music
  (https://pixabay.com/music/summer-vibes-12345/)
  License: Pixabay License (free, no attribution required)
  Duration: 45s, trimmed to 30s
  Saved: vault/clients/acme/deliverables/tiktok-campaign/audio/tiktok-campaign-bg-music.mp3
```

## Output

Return:
- **Track name:** title of the selected track
- **Source:** which library it came from (Pixabay, Free Music Archive, or generated)
- **License:** license type and whether attribution is required
- **File path:** absolute path to the final audio file
- **Duration:** duration of the final file in seconds
- **Format:** sample rate, channels, bitrate
- **Processing applied:** what conversions, trimming, or normalization was done

## Error Handling

- **FFmpeg not installed:** Report the error and instruct the operator to install FFmpeg (`brew install ffmpeg` on macOS). Do not proceed without it — audio processing requires FFmpeg.
- **ffprobe not installed:** FFprobe ships with FFmpeg. Same resolution as above.
- **No tracks match the mood/genre:** Broaden the search terms. Try synonyms (e.g., "happy" instead of "upbeat", "ambient" instead of "chill"). If still nothing, fall back to Source 3 (generated audio) and flag it.
- **Download fails:** Retry once. If it fails again, try the next source in the cascade. Log the failure.
- **File is corrupt (ffprobe fails):** Delete the file, re-download. If the second download is also corrupt, move to the next source.
- **Track is too short:** Search for a longer track. If nothing is available at the required duration, loop the track using FFmpeg:
  ```bash
  # Loop a track to reach the target duration
  ffmpeg -stream_loop -1 -i short.mp3 -t {duration_seconds} -c copy looped.mp3
  ```
  Note in the work log that the track was looped.
- **License unclear:** Do not use the track. Only use tracks with a clearly stated royalty-free or Creative Commons license. When in doubt, skip it.

## See Also

- [[creative-brief]]
- [[source-capability]]
