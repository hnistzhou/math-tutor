# Stage 3: Manim Code Generation
## Output Resolution: 720p (1280×720)
## Generation Principles
- One Scene per frame: `Frame{id}Scene`
- Choose APIs based on `visual_intent`
- Target 5th grade: bright colors, clear animations, readable text
## Required Comments (Every Scene)
```python
class Frame2Scene(Scene):
    # === Value Source Self-Check ===
    # AB = 6  ← Stage 1 explicit_constraints["lengths"]["AB"]
    # CD = 4  ← Stage 1 explicit_constraints["lengths"]["CD"]
    # BC = 8  ← Stage 1 explicit_constraints["lengths"]["BC"]
    # Area = (6+4)/2 × 8 = 40  ← Formula
    # Student error = 6+4×8 = 38 ← Forgot /2
    # A=[-4,3,0]  ← Stage 1 coords
    # === Must match narration and visuals ===
    def construct(self):
        ...
`` ```
## Required Elements (Geometry Frames)
- Draw base figure with ALL vertex labels at start
- Label size ≥24, white color
- Overlay frame-specific highlights/auxiliary lines/text
- NEVER FadeOut vertex labels
## Coordinate Fidelity
- Use `figure_description.suggested_manim_coords` as base
- Validate geometric constraints before use:
  1. Check right angles are actually 90°
  2. Adjust non-critical vertices if needed
  3. For right trapezoids: horizontal base, vertical sides
## Split Layout (layout: "split")
- Left half (x ∈ [-7.1, 0]): Geometry
- Right half (x ∈ [0, 7.1]): Title + equations
- Content safe zones: Left [-6.5, -0.2], Right [0.2, 6.5]
## Left Half Fit Algorithm
```python
import numpy as np

# 1. Collect all geometry points
all_pts = np.array(list(stage1_coords.values()))

# 2. Calculate current bounds
bbox_min = all_pts.min(axis=0)
bbox_max = all_pts.max(axis=0)
bbox_cx = (bbox_min[0] + bbox_max[0]) / 2
bbox_cy = (bbox_min[1] + bbox_max[1]) / 2
bbox_w = bbox_max[0] - bbox_min[0]
bbox_h = bbox_max[1] - bbox_min[1]

# 3. Calculate scale for left safe zone (6.3 × 7.0)
SAFE_W, SAFE_H = 6.3, 7.0
scale = min(SAFE_W / max(bbox_w, 0.1), SAFE_H / max(bbox_h, 0.1), 1.0)

# 4. Translate to left center (-3.5, 0)
target_cx = -3.5
dx = target_cx - bbox_cx * scale
dy = 0 - bbox_cy * scale

# 5. Apply transform
def transform(pt):
    return np.array([pt[0]*scale + dx, pt[1]*scale + dy, 0])
```
## Two-Stage Rendering
1. **Preview** (480p15fps, `--quality preview --workers 4`): 3-10s/frame → ~1-2min total for validation
2. **Medium** (720p30fps, `--quality medium --workers 4`): 10-60s/frame → after validation passes

## Pre-Validation (Automatic)
`render_manim.py` runs pre-checks before any rendering:
- Python syntax check
- LaTeX dependency (MathTex/Tex requires local LaTeX → replace with Text() if not installed)
- Common color arg errors: `.set_color(color=X)` → `.set_color(X)`

Fix errors before rendering to avoid wasted render cycles.
