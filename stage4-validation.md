# Stage 4: Vision Validation
## Frame Extraction
```bash
python scripts/extract_frames.py \
  --video /tmp/frame_{id}_preview.mp4 \
  --output /tmp/keyframe_{id}.png \
  --timestamp middle
```
## Layout Pre-check
```bash
python scripts/check_layout.py --image /tmp/keyframe_{id}.png --frame-id {id}
```
## Tiered Validation Strategy
| Condition | Action | Token Savings |
|-----------|--------|---------------|
| check_layout fails | Skip Vision, go to fix | ~500-800 |
| check_layout passes + has_geometry: false | Skip Vision, pass | ~500-800 |
| check_layout passes + has_geometry: true | Full Vision validation | Standard |
## Validation Checklist
**Basic (All Frames)**
1. Numbers match problem conditions?
2. 5th grader can understand?
3. Visual matches `visual_intent`?
4. No text/shape overlap?
5. No content clipped?

**Geometry Frames**
6. Shape matches original image?
7. Right angles actually 90°?
8. Edge ratios correct?
**Last 2 Frames**
9. Final answer matches problem?
10. Error explanation covers key mistake?
## Failure Handling
- **Pass**: Keep frame, continue
- **Fail**: Regenerate code with feedback, re-render
- **3 Fails (BLOCKING)**:
  1. STOP pipeline
  2. Show failure screenshot + errors
  3. Ask user:
     - [1] Skip frame (use static image)
     - [2] Provide fix guidance
     - [3] Abort
## Diff-Patch Fix Strategy
```
Fix prompt:
"Frame {id} has issues, output only modified code:

Issues: {specific problem}
Original code:
{relevant 1-2 functions}

Format:
[REPLACE: {function name}]
{modified code}
[END]
```
Merge by replacing `[REPLACE]` blocks into original code.
## Geometry Fix Strategies
1. **Right angle issues**: Use `fix_right_angles()` to recalculate
2. **Shape mismatch**: Re-read `figure_description`, check transforms
3. **Proportion issues**: Recalculate from `known_conditions`
