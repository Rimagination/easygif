---
name: easygif
description: Turn natural-language requests and still images into adaptive, validated motion assets. Infer safe motion when needed, preserve subject and scene invariants, choose grid, layer, keyframe, video, or interpolation routes, and produce GIF, WebP, MP4, sprite, layered, contact-sheet, or PNG-frame outputs under aspect-ratio and byte constraints.
---

# EasyGIF

Convert a natural-language visual request into a structured asset plan, an image-generation prompt, deterministic post-processing steps, and validated deliverables.

## Workflow

1. Parse the request into the Prompt IR described in references/prompt-ir.md.
2. Infer the intended use, visual language, motion, background, source dimensions, and output constraints. Treat the scene and object vocabulary as open-ended; do not force the request into a fixed asset category.
3. Build a Motion IR using references/motion-ir.md. Describe scope, motion family, continuity, targets, the approved region or mask, invariants, base-layer policy, timeline, loop behavior, and representation before choosing tools.
4. If the user has not specified an action, act as a motion director: read references/motion-director.md, infer a small number of plausible motions from the image, select one primary motion plus limited micro-motions, and state the choice before composing the prompt.
5. Read only the relevant visual-language references under references/visual-language/ and compose a concise prompt. Preserve explicit user constraints; add inferred details only when they materially improve the result.
6. Use the available image-generation capability for source imagery. For reference-guided work, keep the reference subject/style/layout invariants explicit in every iteration.
7. Probe local optional backends with scripts/probe_backends.py, then select the generation strategy using references/generation-strategy.md, references/backend-capabilities.md, and scripts/select_strategy.py. Save the JSON route plan; it is the source of truth for backends, fallbacks, validators, and repair policy:
   - use scripts/select_strategy.py for a compact, auditable route recommendation;
   - for simple short loops, chat stickers, and low-risk expressions, prefer one generated contact sheet or sprite sheet;
   - for bounded local motion, prefer a static base plus patches or masked edits; use local keyframes and the optional FILM backend only inside the approved region when continuity requires it;
   - for complex motion or cinematic continuity, use independent keyframes and prefer the optional FILM interpolation backend when the local FILM environment is available;
   - use a video workflow only when the motion cannot be represented by keyframes plus interpolation;
   - after a contact sheet is generated, run scripts/validate_grid_geometry.py against the planned rows, columns, and source aspect before treating it as animation frames;
   - if the grid fails validation or the frames contain merged/cross-cell content, fall back to independent generation.
8. Choose a deterministic pipeline:
   - fixed-cell animation or game assets: scripts/slice_grid.py, then frame validation and GIF/WebP preview;
   - independent opaque keyframes with gentle continuous motion: run scripts/film_interpolate.py with the project-local FILM environment, then scripts/compose_gif.py and scripts/optimize_gif.py;
   - existing video or dense motion: extract frames with the host's video tooling, then validate and assemble;
   - video input for a direct chat GIF: use scripts/video_to_gif.py, then validate the result;
   - local layer or masked edit: use scripts/composite_layers.py, then scripts/region_validate.py before encoding;
   - transparent subject: use the built-in chroma-key/background-removal path first, then inspect edge spill;
   - ordinary cinematic visuals: prefer MP4/WebM and create GIF only as a preview or when requested;
   - chat stickers: use short looping output, small dimensions, palette optimization, and aspect-preserving contain fit by default.
9. If the user has not specified a motion, compile a conservative starting recipe with scripts/motion_recipe.py. Replace its subject and region hints after inspecting the image; do not present the recipe as if it were semantic image segmentation. Generate a timeline with scripts/motion_timeline.py when timing or keyframe count is not explicit. Prefer phase-weighted timing with rest, anticipation, action, peak, return, and settle instead of equal frame spacing. When a grid is useful, run scripts/grid_plan.py with role `generation` for a one-pass image/contact sheet or role `packaging` for existing frames, video, or interpolation output. Infer the active frame count and rows×columns from the Motion IR and source/canvas aspect ratio; never assume 3×3.
10. Use scripts/media_budget.py to preserve source aspect ratio and choose a candidate output size under the stated byte budget. Verify the actual encoded file; the estimate is not a guarantee.
11. Run scripts/temporal_validate.py on generated keyframes or dense frames. For local or clustered motion, also run scripts/region_validate.py against the approved region. Inspect any spike boundaries or outside-region violations and either revise the keyframe plan, tighten the mask, localize the edit, or fall back to a simpler representation.
12. Run scripts/validate_output.py on every final asset with `--json`, checking actual bytes, format, frame count, loop metadata, alpha, and source aspect. Use scripts/optimize_gif.py with `--max-bytes` for chat/GIF budgets; its estimate is not a substitute for the encoded-file check.
13. Write a manifest beside each final output with scripts/write_manifest.py. Include the route plan and every validation report. Report assumptions and any remaining visual limitations.
14. When a validation stage fails, run scripts/repair_plan.py before regenerating. Follow its route recommendation: geometry failures require replanning/regeneration, temporal spikes require timeline/keyframe repair, region failures require mask/patch repair, and budget failures are handled only after visual validation.

## Decision rules

- Ask a question only when a missing constraint can invalidate the result, such as an unknown transparency requirement or target platform with incompatible dimensions.
- If the request is ambiguous but recoverable, generate a small set of visual directions rather than inventing a long prompt.
- Keep creative description separate from technical instructions such as frame count, grid geometry, dimensions, FPS, and output format.
- Prefer a single canonical subject reference for every animation row or frame set.
- Never claim that a generated grid is correctly aligned until the crop and validation scripts have confirmed it.
- Never crop or stretch a generated frame to repair a grid-aspect mismatch unless the user explicitly asks for reframing. Regenerate the atlas or use an aspect-preserving contain fit with padding.
- Treat a contact sheet as an efficiency optimization, not as a promise of perfect frame consistency.
- Keep generation prompts explicit about grid rows, columns, cell boundaries, identical camera/framing, and no cross-cell elements.
- Do not use FILM for transparent assets: its RGB output does not preserve alpha. Keep transparent pets on the grid or mask-based path.
- Use FILM only after keyframes have the same subject identity, camera, background, and dimensions. Interpolation smooths motion; it does not correct inconsistent keyframes.
- Treat video as the preferred motion source when the user provides one; do not regenerate a video from stills unless requested.
- When inventing motion, prefer one readable action over many simultaneous actions. Preserve the source image's medium: illustrated images should use limited animation, not photorealistic deformation.
- Do not maintain a closed list of supported scenes. Extend the semantic target vocabulary as needed while routing by Motion IR dimensions.
- Prefer phase-based timelines with rest, anticipation, action, peak, hold, return, and rest when the user gives no timing.
- Choose contact-sheet grid geometry automatically. Treat the requested frame count as a soft target unless the user explicitly requires an exact number; use padding cells only for rest or hold poses.
- Prefer independent keyframes or local layers when the planner reports that contact-sheet cells are too small for the moving detail.
- Treat 4×4/16 cells as a practical upper candidate for generic single-pass image generation, not as a universal optimum. Allow denser 5×5/6×6 layouts mainly for packaging or specialized sprite models.
- Separate generated/keyframe count from playback frame count: use timing, holds, and interpolation to make a short clean source sequence feel fluid.
- Treat a large adjacent-frame difference as a planning failure first, not as a reason to increase interpolation strength.
- For local or clustered motion, keep a static base layer and require an explicit region, bounding box, or mask. Do not redraw the whole scene when a patch can express the action.
- Treat outside-region drift as a hard validation signal: fix the region/mask or keyframes before optimizing GIF size.

## Prompt construction

Use the labeled prompt structure from references/prompt-ir.md. Include intended use, subject, scene, style/medium, composition, lighting/mood, palette, materials, motion, and constraints. Keep the prompt short when the user is already specific.

When motion is inferred rather than supplied, record the motion concept in the
manifest and explain the primary motion, secondary micro-motions, locked
elements, and why the selected route is likely to be stable.

## Bundled scripts

- scripts/slice_grid.py: crop a fixed rows by columns atlas into numbered frames.
- scripts/atlas_to_gif.py: crop a contact sheet and assemble the frames into a GIF/WebP in one deterministic command.
- scripts/compose_gif.py: assemble an ordered frame directory into a looping GIF or animated WebP.
- scripts/optimize_gif.py: resize and palette-optimize an animated GIF for chat sticker limits.
- scripts/film_interpolate.py: run local FILM on ordered opaque keyframes to create smooth intermediate frames.
- scripts/select_strategy.py: recommend contact-sheet, keyframe/FILM, video, or alpha-safe routing from task flags.
- scripts/video_to_gif.py: extract, resize, retime, palette-optimize, and loop an existing video as a GIF.
- scripts/motion_timeline.py: expand a phase-based action plan into frame timestamps.
- scripts/grid_plan.py: infer frame count and choose adaptive rows×columns geometry for generation or packaging roles.
- scripts/validate_grid_geometry.py: reject atlas dimensions or cell aspect ratios that disagree with the plan before slicing.
- scripts/media_budget.py: suggest aspect-preserving dimensions under a byte budget.
- scripts/temporal_validate.py: detect frame-size mismatches and abrupt temporal difference spikes.
- scripts/composite_layers.py: apply ordered local RGBA patches or masked full-frame edits to a static base.
- scripts/region_validate.py: measure whether adjacent changes stay inside an approved region.
- scripts/validate_output.py: check image readability, dimensions, frame counts, alpha presence, and basic animation metadata.
- scripts/motion_recipe.py: compile a conservative, object-agnostic motion concept when the user supplies no action.
- scripts/write_manifest.py: record the media, route, motion concept, and validation reports beside an output.
- scripts/repair_plan.py: convert failed validation reports into the next safe repair route.
- scripts/probe_backends.py: detect optional local encoders, ffmpeg, and FILM assets without installing anything.

## Local FILM backend

When available, use the project-local environment and assets:

    .local/tools/film-venv/Scripts/python.exe
    .local/tools/frame-interpolation
    .local/models/film/film_net/Style/saved_model

Example:

    .local/tools/film-venv/Scripts/python.exe scripts/film_interpolate.py KEYFRAMES OUT \
      --model .local/models/film/film_net/Style/saved_model \
      --film-repo .local/tools/frame-interpolation --times 1

Use `--times 1` for a modest 2x frame count and `--times 2` only when the
motion is gentle and the extra CPU cost is acceptable. If the environment or
model is missing, fall back to the contact-sheet or ordinary keyframe path.
