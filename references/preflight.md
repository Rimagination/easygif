# Production preflight

Before calling image generation, video generation, FILM, encoding, or a
destructive repair, create and expose a compact production card. This is a
planning step, not a new user-facing mode.

## Production card

```text
Goal: <what the final asset is for>
Subject/reference: <what must remain recognizable>
Reference source: <user-provided | generated | video-first-frame>
Reference status: <locked | needs-user-selection>
Reference confidence: <high | medium | low>
Primary motion: <one readable action in chronological beats>
Micro-motions: <zero, one, or two supporting motions>
Locked invariants: <identity, camera, background, style, topology, aspect>
Representation: <full-frame | trusted local patch | contact sheet | keyframes | video>
Generation plan: <how many generated/key frames, grid geometry if any>
Playback plan: <fps, holds, easing, loop boundary>
Delivery contract: <format, dimensions, byte budget, transparency, final output path>
Risks and avoid list: <specific failure modes>
Validation gates: <geometry, temporal, region/composite, output, package>
```

## Rules

1. Resolve the reference stage before invoking any generator or encoder:
   - a supplied still becomes the canonical reference directly;
   - a supplied video uses one representative first/key frame as the canonical
     still, while the video remains the temporal source;
   - without an input image, generate one canonical still before animation;
   - when the subject, style, or scene is vague enough that identity cannot be
     selected confidently, generate 2-3 still candidates and set status to
     `needs-user-selection`; pause before expensive animation;
   - if the user explicitly asks to proceed without confirmation, auto-lock the
     best candidate and record that choice in the manifest.
   Never use a 3x3/4x4 atlas as the canonical identity reference: it is an
   animation source, not a stable reference.
2. Inspect the input and resolve the production card before invoking any
   generator or encoder. Do not ask the user to design the motion when a safe
   interpretation is available; state the interpretation and proceed.
3. Keep one primary motion. Use at most two micro-motions, and state which
   pixels or semantic regions they affect.
4. Separate generated frame count from playback frame count. Use holds and
   easing for rhythm; do not ask a one-pass image model for unnecessary dense
   frames.
5. State the route before execution. A semantic phrase such as “only the hand
   moves” does not authorize local compositing without an explicit mask, alpha
   patch, or deterministic transform.
6. State the repair order before generation: geometry and identity first,
   temporal continuity second, byte optimization last.
7. Treat contact sheets, sliced frames, and source GIFs as staging artifacts.
   Run the final delivery validator/encoder before reporting success; the user
   should receive the validated final path and actual byte count, not only a
   preview or intermediate file.
8. After execution, report the result beside the production card and list any
   assumption that remains visually unverified.

## Cat-yawn example

```text
Goal: short chat sticker / looping GIF
Subject/reference: one hand-drawn cat, same face and body silhouette
Reference source: generated
Reference status: locked
Reference confidence: high
Primary motion: settle → eyelids lower → jaw opens → yawn peak → jaw closes → settle
Micro-motions: small chest rise; tiny head tilt back, both eased and symmetric
Locked invariants: cat identity, ears, whiskers, camera, background, linework, palette
Representation: full-frame 3x3 contact sheet, then deterministic slice and encode
Generation plan: 9 ordered cells, with rest/peak/settle poses and no cross-cell elements
Playback plan: slow 8–10 fps equivalent, longer rest and peak holds, seamless loop
Delivery contract: GIF, square chat canvas, actual byte validation
Risks and avoid list: rotating ears, asymmetric eyes, mouth popping open, frame-to-frame redraw
Validation gates: grid geometry, temporal spikes, output dimensions, loop metadata, byte budget
```
