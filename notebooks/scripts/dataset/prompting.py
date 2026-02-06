from __future__ import annotations


def build_diversify_prompt(script: str, n_variants: int, parameters) -> str:
    return f"""
You are given a Blender Python script that creates a specific 3D model. Your task is to generate {n_variants} diverse but functionally equivalent variants of this script. Each new variant must result in roughly the same 3D geometry in Blender, but the code should be structurally and stylistically different from the original and from each other.

To meaningfully diversify the code, apply at least 2 or more of the following strategies per variant:
- Rename variables and constants (using meaningful alternatives)
- Extract logic into helper functions or classes to promote modularity
- Reorder operations when the order does not affect the final geometry
- Change from procedural to object-oriented or functional programming style
- Use parenting, collections, or modifiers (only if the final geometry remains the same)
- Rewrite comments for clarity or variety
- Change color or scale of the object

You may rewrite how the geometry is constructed if it still results in the same final 3D output. For example, using different Blender operators or functions is allowed only if they are guaranteed to produce identical geometry. Keep the scripts concise.
Maintain import packages at the top of the script along with the lines to clear the scene. Output exactly {n_variants} variants in the following JSON format:
[
  {{
    "variant_id": "variant_1",
    "code": "'''python [...code...] '''"
  }},
  ...
]

Here is the script:
{script}

{parameters}
""".strip()


def build_reasoning_prompt(target_code: str, descript: str, example: str) -> str:
    return f"""
Your task is to rewrite a Blender Python script in a step-by-step, reasoning-oriented format.

Instructions:
- Break down the code into logical chunks.
- For each chunk, explain briefly what it does.
- Follow that explanation with a code block showing just that part.
- At the end, show the full final script in one code block.
- Output only your reasoning and code blocks — do not add anything else.

Here is an example of how to do this:
{example}

Now apply the same reasoning format to the following Blender code that makes a {descript}:
{target_code}
""".strip()
