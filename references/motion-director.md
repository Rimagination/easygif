# Motion director

Use this reference when the user asks to animate a still image but does not
specify an action or motion prompt.

## Procedure

1. Read the image as a scene, not as a collection of isolated objects:
   identify the focal subject, secondary subjects, environment, implied action,
   visual rhythm, and plausible sources of motion.
2. Generate two or three candidate motions internally. Prefer the one that
   adds life while preserving the original composition.
3. Choose one primary motion and at most two secondary micro-motions. Keep the
   camera mostly locked unless a slow push-in or parallax clearly helps.
4. State the chosen motion in concrete chronological beats before writing the
   generation prompt.
5. Mark the smallest practical motion region (bbox or mask) and decide whether
   the action can be expressed as a local patch. If yes, preserve a static base
   layer and keep the region outside the patch unchanged.
6. Lock all non-moving elements explicitly: identity, pose silhouette,
   clothing, architecture, artwork, lighting, perspective, and background.
7. Choose the least fragile route: local patches or masked keyframes for
   bounded motion, keyframes plus FILM for opaque scene-wide motion,
   contact sheet for small/simple changes, and alpha-safe compositing for
   transparent subjects.

Use `scripts/motion_recipe.py` to make the chosen motion explicit when the
user supplied no action. Treat its output as a conservative scaffold, not as
image recognition: replace the subject, region, and locked elements after
inspecting the actual image. Keep the primary motion singular; at most two
micro-motions may reinforce it.

## Motion selection heuristics

Do not use a closed scene list. Inspect the visible affordances and map them to
motion families:

- rigid transform: translate, rotate, scale, swing, orbit, or bob a bounded
  object while preserving its shape;
- articulated: move a linked chain through a plausible joint path;
- deformable: bend, squash, stretch, wrinkle, or ripple while preserving
  topology and material identity;
- periodic: breathe, pulse, flicker, oscillate, or cycle a repeating signal;
- appearance: change light, color, texture, reflection, opacity, or emission;
- camera: pan, tilt, dolly, zoom, parallax, or focus shift while locking scene
  geometry when required;
- environmental: move particles, atmosphere, weather, water, foliage, fabric,
  or other distributed fields;
- relational: make two or more targets respond to one another, with explicit
  cause-and-effect timing.

Use the smallest number of motion families that explains the scene. Any new
object or domain can use these families without adding a new workflow.

## Example: gallery illustration

For an illustrated art-gallery scene with two foreground visitors and two
background visitors, a safe self-directed concept is:

```text
primary: the red-haired visitor makes one small conversational hand gesture;
secondary: the black-haired visitor blinks and shifts her gaze toward the hand;
ambient: the polished floor reflection and gallery light drift very slightly;
camera: locked composition with a barely perceptible breathing motion.
```

Use five to seven opaque keyframes, keep all four people and all paintings in
the same positions, and describe the motion as slow, hand-drawn limited
animation. Avoid walking, turning bodies, changing paintings, or independent
large movements because those are likely to produce identity and geometry
drift in a short GIF.

## Prompt skeleton

```text
Animate this exact illustrated scene as a short seamless loop. Preserve the
original composition, hand-drawn linework, character identities, clothing,
gallery architecture, paintings, perspective, colors, and lighting. Primary
motion: <one action in chronological beats>. Secondary motion: <at most two
micro-motions>. Keep the camera locked. Use slow natural easing, limited
animation, and no new characters or objects. Nothing changes except the stated
motion.
```
