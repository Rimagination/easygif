# Prompt IR

Use this as an internal representation before writing the final image-generation prompt. Omit fields that are genuinely irrelevant.

    {
      "intent": "asset_generation",
      "asset": {
        "subject": "",
        "use_case": "",
        "background": "",
        "motion": "",
        "loop": null
      },
      "visual": {
        "style": "",
        "medium": "",
        "scene": "",
        "composition": "",
        "lighting": "",
        "palette": "",
        "materials": "",
        "mood": ""
      },
      "technical": {
        "frame_count": null,
        "fps": null,
        "grid": null,
        "size": null,
        "outputs": []
      },
      "constraints": [],
      "avoid": []
    }

Compile the fields in this order:

    intended use -> scene/backdrop -> subject -> action/motion -> style/medium
    -> composition -> lighting/mood -> palette/materials -> technical constraints
    -> avoid/negative constraints

For edits and reference-guided generation, state invariants explicitly: change only X; keep Y unchanged.
