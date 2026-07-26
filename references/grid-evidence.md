# Grid and frame-count evidence

Research snapshot: 2026-07-26.

There is no universal best number of frames per image. The evidence separates
animation design from atlas packing and consistently points to three variables:
motion phases, per-cell resolution, and the consistency capability of the
generation method.

## Sources

- [OpenAI sprite-pipeline skill](https://github.com/openai/plugins/blob/main/plugins/game-studio/skills/sprite-pipeline/SKILL.md): uses an approved seed frame, one whole-strip generation pass, exact frame count, shared scale/anchor, and a four-frame recipe for a small animation.
- [Karem505 character-animation-skill](https://github.com/karem505/character-animation-skill/blob/main/SKILL.md): documents 6x6/36-frame single-sheet generation for organic subjects, recommends reducing to 5x5 or 4x4 when identity drifts, and uses per-frame generation plus interpolation for rigid subjects.
- [SpriteForge](https://github.com/tantk/spriteforge-pipeline): packages 16 frames as a 4x4, 1024x1024 atlas with 256x256 cells, while noting that a generic model can lose consistency across 16 frames and that a template/LoRA improves it.
- [Sprite Sheet Diffusion](https://arxiv.org/abs/2412.03685): treats the problem as a reference character plus an explicit pose sequence, with temporal stability as a model capability rather than a fixed grid-size rule.
- [Sprite-AI frame-count discussion](https://www.sprite-ai.art/blog/sprite-animation-frames): gives experience-based ranges of 2–4 frames for idle, 4–8 for walk, 6–8 for run, and 3–6 for attacks, and emphasizes timing/holds over simply adding drawings.

## Operational conclusion

For a generic image model, start with 4–9 active frames. Use 4x4/16 only
when the subject is stable, the cells remain large enough, or the output is a
template-driven sprite sheet. Use 5x5/6x6 as a packaging layout for already
generated frames, video, interpolation output, or a model trained for dense
sprite sheets. If the motion needs more playback frames, keep the generated
source modest and add in-betweens or variable frame durations downstream.
