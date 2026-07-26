# Backend capabilities

Use backend names as capability labels, not as hard-coded scene modes. The
planner may replace a backend when it is unavailable or when validation fails.

| Backend | Best at | Do not assume |
|---|---|---|
| `imagegen_contact_sheet` | Low-amplitude motion with few frames and one generation call | Perfect identity, readable tiny cells, or exact cell geometry |
| `validated_grid_slice` | Turning an approved atlas into ordered frames | Repairing a bad atlas; geometry must pass first |
| `local_rgba_composite` | Bounded motion with a static base and transparent patches | Solving large topology changes or camera motion |
| `keyframe_generator` | Articulated, deformable, relational, or narrative motion | Independent frames are automatically consistent |
| `film_opaque` | Smoothing opaque, same-camera keyframes | Transparency, alpha edges, or broken keyframes |
| `film_opaque_crop` | Smoothing a bounded opaque crop before recompositing | Region drift is fixed by interpolation |
| `video_source` / `ffmpeg_extract` | Existing video or dense temporal motion | Loop safety, GIF size, or platform limits |
| `pillow_or_gifski` | Deterministic encoding and byte-budget retries | Inventing motion or repairing semantic errors |

Route through capability axes: alpha, spatial scope, continuity, input source,
frame budget, and target format. When a backend is missing, use the declared
fallback route and record the decision in the manifest.
