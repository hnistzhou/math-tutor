---
name: math-tutor
description: Use when generating teaching videos from math problem images - takes student's incorrect math work photo and creates 2-3 minute video explaining why they made the mistake
---

# Math Tutor Skill

## Overview

Generate teaching videos from math problem images for 5th grade students. Takes a photo of student's incorrect work, identifies the error, and creates a 2-3 minute video explaining the mistake and correct solution.

## When to Use

- User provides a math problem image (photo/screenshot) with error explanation
- User mentions "错题讲解", "teaching video", "explain the mistake"
- Need to create visual math animation with narration

## Core Pipeline

```
Image → Stage 1: Vision Analysis → Stage 2: Storyboard → Stage 3A/3B: Manim + TTS (parallel) → Stage 4: Vision Validation → Stage 5: Video Composition
```

## Stage Summary

| Stage | Purpose | Output |
|-------|---------|--------|
| 1 | Analyze image, extract geometry constraints | JSON with coordinates, constraints |
| 2 | Generate storyboard with narration | Frames JSON with visual_intent |
| 3A | Render Manim animation | MP4 per frame |
| 3B | Synthesize voice (CosyVoice 2) | MP3 per frame |
| 4 | Vision validation + fix loop (≤3) | Validated frames |
| 5 | FFmpeg composition | Final output.mp4 |

## Key Scripts

```bash
# Render Manim
python scripts/render_manim.py /tmp/animation.py --quality preview

# Synthesize voice
python scripts/synthesize_voice.py --text "..." --frame-id 1 --output /tmp/audio_1.mp3

# Extract keyframes for validation
python scripts/extract_frames.py --video /tmp/frame.mp4 --output /tmp/keyframe.png

# Compose final video
python scripts/compose_video.py --storyboard /tmp/storyboard.json --output ./output.mp4
```

## Critical Rules

1. **Iteration limit**: Stage 1 (vision analysis) allows 3 iterations max
2. **Fix loop**: Stage 4 allows 3 fix attempts per frame
3. **Blocking on 3 failures**: If a frame fails 3 times, MUST pause and ask user (never silent degradation)
4. **Explicit > Visual > Inferred**: Constraint priority in geometry analysis
5. **Two-stage rendering**: Preview (480p) for validation → Medium (720p) for final

## Common Mistakes

- Skipping vision validation → Always extract keyframes and validate
- Not checking geometry constraints → Use `validate_geometry_analysis()` before generating coords
- Silent degradation on failures → MUST ask user after 3 failures

## References

- @stage1-analysis.md - Detailed Stage 1 analysis with iteration logic
- @stage2-storyboard.md - Storyboard format and validation checklist
- @stage3-manim.md - Manim code templates and layout rules
- @stage4-validation.md - Vision validation checklist and fix strategies
- @scripts/README.md - Script usage documentation
