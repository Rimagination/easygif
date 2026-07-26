# Generation strategy

Choose the least expensive strategy that still protects visual quality.

## Automatic routing

Use `scripts/select_strategy.py` with the Motion IR axes. The result is
guidance, not a substitute for inspecting frames. Route by capability rather
than by object or scene names. If a contact sheet is selected, run
`scripts/grid_plan.py` (or use its embedded `grid_plan` result) instead of
assuming a fixed 3x3 layout:

Save the complete JSON result. It declares backend candidates, fallbacks,
validators, and a repair policy; do not silently switch representations after
a failed check.

```text
preserve alpha + local scope       -> alpha-safe layers or mask compositing
existing video                     -> video extraction
local + periodic/appearance       -> parametric or local layers
local/cluster + high continuity   -> local keyframes then interpolation
articulated/deformable/relational -> planned full-frame keyframes then interpolation
low continuity + few frames       -> validated contact sheet
```

The grid planner infers a compact active-frame count from continuity and
motion family, then chooses rows and columns that fit the source/canvas aspect
ratio. It prefers usable layouts such as 2x2, 2x3, 2x4, 3x3, 3x4, and 4x4;
prime or awkward counts may be rounded upward and filled with repeated rest or
hold poses. The planner also reports cell size and warns when contact-sheet
cells are too small for reliable detail.

## Generation grid versus packaging atlas

Do not confuse the number of frames the model must invent with the number of
frames that can be packed into a final atlas:

| Role | Practical default | Use 4x4? | Dense 5x5/6x6 |
|---|---|---|---|
| single-pass image generation | 4–9 active frames; 16 is an upper candidate | yes, when the subject is stable and each cell remains readable | only for organic motion, a dedicated sprite model, or a controlled experiment |
| packaging existing frames/video/interpolation | whatever the source contains | yes | yes, if the atlas contract or engine benefits from it |

The planner therefore uses a 16-cell cap for ordinary one-pass generation and a
36-cell cap for packaging. A 4x4 sheet is not automatically higher quality:
the extra cells reduce per-cell resolution and give a generic image model more
opportunities to drift. For smooth final playback, prefer a modest set of
clean keyframes and interpolation or variable holds over asking one image
model to invent dozens of near-identical drawings.

When a final platform size differs from the source frame ratio, use an
aspect-preserving contain fit with a sampled or explicit background color. A
stretch fit is an explicit exception, never the default; content cropping is
not a geometry repair. For GIF budgets, let `scripts/optimize_gif.py` retry
colors, dimensions, and playback frame count, then validate the actual file
with `scripts/validate_output.py --max-bytes`.

## Contact-sheet-first

Use one generated image containing a strict grid when:

- the request is a short loop with 2–16 frames;
- the subject is a pet, sticker, simple prop, icon, or small game effect;
- the action is limited to blinking, breathing, bobbing, waving, or another low-amplitude motion;
- the user values fewer image-generation calls more than independent full-resolution frames.

Prompt requirements:

    Create a strict 2x2 contact sheet with exactly one frame per cell.
    Use identical camera, subject scale, background, lighting, and framing in every cell.
    Keep every subject fully inside its cell with generous padding.
    Do not add borders, labels, gutters, text, or elements crossing cell boundaries.
    Only change: <specific motion differences>.

After generation:

1. Confirm the image dimensions are divisible by the requested rows and columns.
2. Run scripts/validate_grid_geometry.py with the planned source aspect and
   rows/columns. A square output with a planned 2x3 grid over a square source,
   for example, is a geometry failure because it produces portrait cells.
3. Crop with scripts/atlas_to_gif.py or scripts/slice_grid.py only after the
   geometry check passes. Both tools can repeat the geometry gate when given
   `--source-width/--source-height`; use that guard for direct tool calls.
4. Inspect the contact sheet and at least the first, middle, and last frame.
5. Reject the strategy if the model merged cells, changed identity, or
   changed the intended framing. Do not crop the content to hide the failure.

## Independent-frame fallback

Use separate generation calls when:

- the motion is narrative, cinematic, fast, or physically complex;
- the output needs large full-resolution frames;
- each frame needs different composition or camera movement;
- a contact sheet failed visual inspection;
- the user explicitly requests maximum frame quality or precise per-frame control.

After generating opaque keyframes, use `scripts/film_interpolate.py` with
`--times 1` to insert one midpoint between each pair. Use `--times 2` only for
slow, gentle motion; it quadruples the number of model calls per interval.

## Local-first compositing

When the Motion IR marks the action as `local` or `cluster`, preserve a static
base layer whenever the request does not explicitly require a global change:

1. Resolve the target into a bounding box or mask; keep a semantic description
   in the manifest as well.
2. Generate local RGBA patches, local crops, or full-frame edits with a mask.
3. Use `scripts/composite_layers.py` to place each ordered edit on the same
   base image.
4. If the local edit is continuous, run FILM only on the local crop or patch,
   then composite the interpolated results back onto the base.
5. Run `scripts/region_validate.py` on the composited frames before GIF or
   video encoding. A violation means the region estimate, mask, or keyframe
   plan needs revision; increasing interpolation strength is not a fix.

This route is intentionally object-agnostic. It applies to a hand, eye,
tail, prop, light source, cloud, UI element, brush stroke, or any other
bounded moving region. Fall back to full-frame keyframes only when the motion
changes scene topology, occlusion, camera, or a large fraction of the image.

## Existing video

When the user supplies a video or asks to make a GIF from video, prefer the
video as the motion source. Use `scripts/video_to_gif.py` for a compact chat
GIF, or extract frames first when the user needs editing, looping, or a
transparent/background-removal pass. Do not use FILM on an already dense video
unless a specific slow-motion interpolation is requested.

## Cost and quality trade-off

One contact sheet normally reduces image-generation calls and prompt overhead, but each frame occupies only part of the generated canvas. It can therefore reduce per-frame detail and make grid errors more likely. Do not assume that one contact sheet is always cheaper when the sheet must be much larger or needs multiple retries.

## Representation selection

Choose a representation based on the change, not the subject label:

| Change characteristics | First representation | Fallback |
|---|---|---|
| local, rigid, periodic, or color-only | parametric transform/layer | contact sheet |
| local, articulated, high continuity | masked keyframes + local interpolation | full keyframes |
| scene-wide but low continuity | contact sheet | independent keyframes |
| scene-wide, deformable, or relational | independent keyframes or video | contact sheet |
| existing temporal source | video extraction | keyframes |

If no row fits, keep the Motion IR and choose the least destructive
representation that preserves its invariants. The table is intentionally open:
new scene types should map to these properties rather than create new modes.
