# Motion IR

Motion IR is the neutral description between image understanding and media
rendering. Do not classify a request by a closed list of object or scene names.
Describe what changes, where it changes, how it changes, and what must remain
fixed.

```json
{
  "scope": "local | cluster | global | scene",
  "family": "transform | articulated | deformable | periodic | appearance | camera | environmental | relational | mixed",
  "continuity": "low | medium | high",
  "primary_targets": ["semantic target or region"],
  "secondary_targets": ["optional subtle regions"],
  "region": {"type": "bbox | mask | semantic | none", "value": "approved motion area"},
  "invariants": ["identity, topology, camera, background, palette, alpha"],
  "base_layer": {"enabled": true, "source": "reference | first_frame | generated"},
  "layer_strategy": "patch | masked_full_frame | none",
  "grid": {"mode": "adaptive | fixed | none", "role": "generation | packaging", "rows": null, "cols": null, "active_frames": null, "padding_frames": 0},
  "timeline": ["rest", "anticipation", "action", "peak", "hold", "return", "rest"],
  "loop": {"seamless": true, "cycles": 1},
  "representation": "parametric | layered | contact_sheet | keyframes | video"
}
```

## Routing dimensions

- `scope`: local changes are candidates for masks or compositing only when an
  explicit region/alpha source exists; scene-wide changes need full-frame
  keyframes or video.
- `region`: a semantic target must become a bounding box or mask before
  deterministic compositing. If the region is unknown, use a conservative
  region estimate and validate it before encoding the final asset.
- `family`: rigid transforms can use geometry; articulated/deformable changes
  need planned keyframes; periodic or appearance changes may be synthesized
  without a generative video model.
- `continuity`: high continuity favors dense keyframes or a video source;
  low continuity can use a contact sheet.
- `invariants`: the more invariants there are, the more the pipeline should
  lock camera/background/text in full-frame keyframes or use a trusted static
  base; never invent a pixel mask just to satisfy the invariant.
- `base_layer` and `layer_strategy`: reuse the unchanged base only when the
  route has an explicit patch, alpha, or validated mask. Otherwise keep the
  entire generated frame intact.
- `representation`: select the cheapest representation that can express the
  requested motion without inventing topology.
- `grid`: a contact sheet is an intermediate representation, not a default
  3x3 requirement. When it is selected, infer active frames from motion
  phases and choose rows/cols from the source and canvas aspect ratios. Any
  padding cells must repeat a rest or hold pose. Distinguish a
  `generation` grid (limited by single-pass model consistency) from a
  `packaging` grid (which may be dense because frames already exist).

Unknown or mixed scenes are valid. Add a new semantic target or motion family
without adding a new top-level workflow.

## Local-motion contract

For a local or clustered action, the generated frames must satisfy two
conditions: the approved region changes enough to express the action, and the
pixels outside that region remain stable within a small tolerance. Use
`scripts/composite_layers.py` to enforce the first condition structurally and
`scripts/region_validate.py` plus `scripts/composite_validate.py` to measure
outside drift and mask-edge spill after compositing. These checks apply only
when the representation is explicitly `static_base_plus_patch`.

For a full-frame contact sheet or full-frame keyframe sequence, a local-region
check is diagnostic: it can reveal that the generator changed the background,
but it must not trigger an improvised foreground extraction. Regenerate the
full frame or switch representation instead.
