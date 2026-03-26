# Stage 2: Storyboard Generation

## Format

```json
{
  "problem_type": "geometry",
  "total_duration_estimate": 140,
  "narration_word_count": 320,
  "frames": [
    {
      "id": 1,
      "type": "problem_display|solution_step|error_analysis|summary",
      "narration": "旁白文字",
      "visual_intent": "What to show, natural language description",
      "layout": "split|full",
      "has_geometry": true,
      "duration_hint_sec": 18
    }
  ]
}
```

## Field Definitions

- `has_geometry`: `true` = Vision semantic validation needed; `false` = Layout check only, skip Vision
- `layout`: `"split"` for geometry frames (left graph right math), `"full"` for others

## Validation Checklist
- [ ] Total narration: ≤350 words (normal), ≤500 (complex)
- [ ] Every frame has clear `visual_intent`
- [ ] Solution steps complete, no gaps
- [ ] Geometry: all auxiliary constructions shown
- [ ] Geometry frames: all vertex labels present
- [ ] Error analysis: clearly explains the mistake
- [ ] Language: friendly, encouraging, 5th grade level
- [ ] Layout: `"split"` for geometry solution/error frames

## Design Principles
1. Frame 1: Show problem, present conditions
2. Middle frames: One step per frame
3. Second-to-last: Analyze error ("Kids often...")
4. Last frame: Summarize, encourage
