# Stage 1: Geometry Analysis with Iteration

## Overview

Extract geometry constraints from image using Vision, then generate Manim-compatible coordinates through iterative validation (max 3 rounds).

## Iteration Flow

```
Image → 1.1 Extract → 1.2 Precheck → 1.3 Generate Coords → 1.4 Validate → 1.5 Decision
                                                          ↓ failed & round < 3
                                                   Return to 1.1 with errors
                                                          ↓ passed or round >= 3
                                                   1.6 Output JSON
```

## Token-Saving Strategy

- **Round 1**: Full image + complete analysis prompt
- **Round 2**: Send only `critical_errors` + relevant fields (no re-send image, ~40-60% token savings)
- **Round 3**: Conservative estimates, use defaults for uncertain values

## Stage 1.1: Image Analysis

Extract elements without generating final coordinates:

```json
{
  "iteration": 1,
  "problem_type": "geometry",
  "known_conditions": ["AB=6", "CD=4", "BC=8", "∠B=∠C=90°"],
  "question_ask": "求梯形ABCD的面积",
  "detected_elements": {
    "vertices": ["A", "B", "C", "D"],
    "edges": ["AB", "BC", "CD", "DA"],
    "angles": [{"vertex": "B", "type": "right", "source": "符号标注"}]
  },
  "constraints": {
    "explicit": {"lengths": {"AB": 6}, "angles": [{"vertex": "B", "degrees": 90}]},
    "visual": {"shape_type": "直角梯形"},
    "inferred": {"assumptions": ["AB⊥BC"]}
  }
}
```

## Constraint Priority

1. **explicit_constraints**: Written in problem (highest certainty)
2. **visual_constraints**: Visually detected (may have error)
3. **inferred_constraints**: Deduced (needs verification)

## Stage 1.3: Coordinate Generation

```python
# Example: Right trapezoid with AB=6, CD=4, BC=8, ∠B=∠C=90°

# Step 1: Place base BC centered
BC = 8
B = [-BC/2, -3, 0]   # [-4, -3, 0]
C = [BC/2, -3, 0]    # [4, -3, 0]

# Step 2: AB perpendicular to BC from B
AB = 6
A = [B[0], B[1] + AB, 0]  # [-4, 3, 0]

# Step 3: CD perpendicular to BC from C
CD = 4
D = [C[0], C[1] + CD, 0]  # [4, 1, 0]
```

## Stage 1.4: Programmatic Validation

```python
import numpy as np

def validate_geometry_analysis(coords, constraints, iteration_round):
    errors = []
    warnings = []
    
    # Edge length validation
    def edge_length(p1, p2):
        return np.linalg.norm(np.array(coords[p1]) - np.array(coords[p2]))
    
    for edge, expected in constraints.get('explicit', {}).get('lengths', {}).items():
        if len(edge) == 2 and edge[0] in coords and edge[1] in coords:
            actual = edge_length(edge[0], edge[1])
            error_pct = abs(actual - expected) / expected * 100
            if error_pct > 5:  # 5% tolerance
                errors.append(f"Edge {edge}: expected {expected}, got {actual:.2f}, error {error_pct:.1f}%")
    
    # Angle validation
    def angle_at(vertex, p1, p2):
        v1 = np.array(coords[p1]) - np.array(coords[vertex])
        v2 = np.array(coords[p2]) - np.array(coords[vertex])
        cos_angle = np.dot(v1[:2], v2[:2]) / (np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2]) + 1e-10)
        cos_angle = np.clip(cos_angle, -1, 1)
        return np.degrees(np.arccos(cos_angle))
    
    # Boundary check (zero tolerance)
    for vertex, coord in coords.items():
        if not (-7 <= coord[0] <= 7) or not (-4 <= coord[1] <= 4):
            errors.append(f"Coord out of bounds: {vertex}={coord}")
    
    # Vertex overlap check
    vertices = list(coords.keys())
    for i in range(len(vertices)):
        for j in range(i+1, len(vertices)):
            dist = np.linalg.norm(np.array(coords[vertices[i]]) - np.array(coords[vertices[j]]))
            if dist < 0.5:
                errors.append(f"Vertices overlap: {vertices[i]} and {vertices[j]}, distance={dist:.3f}")
    
    return {
        "passed": len(errors) == 0,
        "iteration": iteration_round,
        "critical_errors": errors,
        "warnings": warnings
    }
```

## Stage 1.5: Iteration Decision

```python
if validation_result["passed"]:
    # Pass → Stage 1.6
    goto_stage_1_6()
elif iteration_round < 3:
    # Fail but can retry → Stage 1.1 with errors
    next_iteration_data = {
        "round": iteration_round + 1,
        "previous_errors": validation_result["critical_errors"]
    }
    goto_stage_1_1(next_iteration_data)
else:
    # 3 failures → abort with user notification
    handle_failure_mode(validation_result)
```

## Common Fix Templates

### Fix Right Angle
```python
def fix_right_angle(coords, vertex, leg1, leg2):
    """Adjust leg2 to make vertex a right angle, keeping leg1 and vertex fixed"""
    v = np.array(coords[vertex])
    a = np.array(coords[leg1])
    b = np.array(coords[leg2])
    
    va = a - v
    vb = b - v
    
    perp = np.array([-va[1], va[0], 0])
    length_vb = np.linalg.norm(vb[:2])
    if np.linalg.norm(perp[:2]) > 0.001:
        perp = perp / np.linalg.norm(perp[:2]) * length_vb
        coords[leg2] = v + perp
    
    return coords
```

### Enforce Edge Length
```python
def enforce_edge_length(coords, p1, p2, target_length):
    """Adjust p2 so |p1-p2| = target_length"""
    a = np.array(coords[p1])
    b = np.array(coords[p2])
    
    direction = b - a
    current_length = np.linalg.norm(direction[:2])
    
    if current_length > 0.001:
        new_b = a + direction / current_length * target_length
        coords[p2] = new_b
    
    return coords
```

### Center and Scale
```python
def center_and_scale(coords, target_bbox=(-6, -3.5, 6, 3.5), margin=0.8):
    """Center and scale figure to fit screen"""
    points = np.array(list(coords.values()))
    
    min_xy = points.min(axis=0)[:2]
    max_xy = points.max(axis=0)[:2]
    center = (min_xy + max_xy) / 2
    
    for k in coords:
        coords[k][:2] -= center
    
    current_size = max_xy - min_xy
    target_size = np.array([target_bbox[2] - target_bbox[0], 
                           target_bbox[3] - target_bbox[1]]) * margin
    scale = min(target_size / (current_size + 1e-10))
    
    for k in coords:
        coords[k][:2] *= scale
    
    return coords
```
