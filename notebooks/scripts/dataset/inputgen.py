from __future__ import annotations
import random

# === WORD BANKS ===

verbs = ["Write", "Create", "Generate", "Make", "write", "create", "generate", "make"]
verbs = ["Write", "Generate", "write", "generate"]
mediums = [
    "Blender code", "a Blender script", "Blender Python script", "blender python code",
    "code in Blender", "blender code", "blender script", "python blender code", 
    "a blender code", "a Blender code"
]

targets = ["{shape}.", "a model of {shape}.", "{shape}", "a model of {shape}"]

actions_to = ["create", "generate", "build", "construct", "make"]
actions_that = ["that creates", "that generates", "that builds", "that constructs", "that makes"]
actions_that = ["to create", "to make", "that creates", "that makes"]

actions_base = ["create", "generate", "build", "construct", "make"]
actions_3s = [v + "s" if not v.endswith("e") else v[:-1] + "es" for v in actions_base]
actions_ing = [v + "ing" if not v.endswith("e") else v[:-1] + "ing" for v in actions_base]
joiners = ["in", "using"]

intro_phrases = [
    "Using {medium},", "With {medium},", "By using {medium},",
    "using {medium},", "with {medium},", "by using {medium},",
    "Using {medium}", "With {medium}", "By using {medium}",
    "using {medium}", "with {medium}", "by using {medium}"
]

format_c_templates = [
    "{medium} to {action} {target}",
    "{medium} that {action_3s} {target}",
    "{medium} for {action_ing} {target}"
]

# === FORMAT FUNCTIONS ===

def format_a(shape):
    verb = random.choice(verbs)
    medium = random.choice(mediums)
    action = random.choice(actions_that)
    target = random.choice(targets).format(shape=shape)
    return f"{verb} {medium} {action} {target}"

def format_b(shape):
    medium = random.choice(mediums)
    intro = random.choice(intro_phrases).format(medium=medium)
    action = random.choice(actions_to)
    target = random.choice(targets).format(shape=shape)
    return f"{intro} {action} {target}"

def format_c(shape):
    medium = random.choice(mediums)
    template = random.choice(format_c_templates)
    target = random.choice(targets).format(shape=shape)

    if "{action}" in template:
        action = random.choice(actions_base)
        return template.format(medium=medium, action=action, target=target)
    elif "{action_3s}" in template:
        action_3s = random.choice(actions_3s)
        return template.format(medium=medium, action_3s=action_3s, target=target)
    elif "{action_ing}" in template:
        action_ing = random.choice(actions_ing)
        return template.format(medium=medium, action_ing=action_ing, target=target)

def format_d(shape):
    action = random.choice(actions_to)
    if random.random() < 0.5:
        action = action.capitalize()
    target = random.choice(targets).format(shape=shape).rstrip(".")
    joiner = random.choice(joiners)
    medium = random.choice(mediums)
    return f"{action} {target} {joiner} {medium}"

# === MASTER PROMPT GENERATOR ===

formats = [format_a, format_b, format_c, format_d]
def generate_input(shape):
    """Generates a prompt string for a given shape."""
    return random.choice(formats)(shape)


##### CELLULAR #########

cell_core_phrases = {
    "cellular_generic": [
        "a cellular bioinspired material",
        "a cellular bioinspired cube",
        "a cellular bioinspired structure",
    ],
}

cell_modifier_phrases = {
    "cellular_sandwich": [
        "with sandwich layers",
        "with layers on top and bottom",
        "with sandwich top and bottom layers"
    ],
    "cellular_voronoi": [
        "with smooth edges",
        "with smooth curves",
        "smoothed"
    ]
}

def generate_cell_phrase(base_id):
    if base_id == "cellular_vorosand":
        core = random.choice(cell_core_phrases["cellular_generic"])
        voronoi_modifier = random.choice(cell_modifier_phrases["cellular_voronoi"])
        sandwich_modifier = random.choice(cell_modifier_phrases["cellular_sandwich"])
        modifiers = [voronoi_modifier, sandwich_modifier]
        random.shuffle(modifiers)
        return f"{core} {modifiers[0]} and {modifiers[1]}"

    elif base_id in cell_core_phrases:
        core = random.choice(cell_core_phrases[base_id])
        modifiers = []

        for mod_base_id, mod_list in cell_modifier_phrases.items():
            if mod_base_id in base_id:
                modifiers.append(random.choice(mod_list))

        if modifiers:
            return f"{core} {' '.join(modifiers)}"
        else:
            return core

    elif base_id in cell_modifier_phrases:
        core = random.choice(cell_core_phrases["cellular_generic"])
        modifier = random.choice(cell_modifier_phrases[base_id])
        return f"{core} {modifier}"

    else:
        raise ValueError(f"Unknown base_id: {base_id}")
    



######## HELICAL #############
hel_core_phrases = {
    "helical_generic": [
        "a helical bioinspired structure",
        "a helical twisted ply bioinspired structure",
        "a helical Bouligand bioinspired structure",
        "a helical stacked bioinspired structure",
        "a helical bioinspired material",
        "a helical twisted ply bioinspired material",
        "a helical Bouligand bioinspired material",
        "a helical stacked bioinspired material"
    ]
}

hel_modifier_phrases = {
    "helical_noise": [
        "with noise",
        "with noise in each rotation",
        "with angular variation per ply",
        "with randomness in rotation",
        "with rotational noise"
    ],
    "helical_rectfibers": [
        "made of rectangular fibers",
        "where each ply consists of rectangular fibers",
        "with flat rectangular struts in each layer",
        "with each layer formed by rectangular fibers"
    ],
    "helical_cylinfibers": [
        "made of cylindrical fibers",
        "where each ply consists of cylindrical fibers",
        "with cylindrical rods forming each layer",
        "with each layer composed of aligned cylinders"
    ]
}

def generate_hel_phrase(base_id):
    if base_id in hel_core_phrases:
        return random.choice(hel_core_phrases[base_id])

    elif base_id in hel_modifier_phrases:
        # Always use helical_generic as the base for helical modifiers
        base = random.choice(hel_core_phrases["helical_generic"])
        modifier = random.choice(hel_modifier_phrases[base_id])
        return f"{base} {modifier}"

    else:
        raise ValueError(f"Unknown base_id: {base_id}")
    

####### TUBULAR #############

tub_core_phrases = {
    "tubular_generic": [
        "a tubular bioinspired material",
        "a tubular porous bioinspired material",
        "a tubular bioinspired structure",
        "a tubular porous bioinspired structure",
        "a cube of tubular bioinspired material",
    ]
}

tub_modifier_phrases = {
    "tubular_layers": [
        "with layers",
        "with cortical layers",
        "with layers around each tubule",
        "with tubule layers",
    ],
    "tubular_noise": [
        "with random placement",
        "with jittered placement",
        "with noisy tubule placement",
        "with noise"
    ]
}

def generate_tub_phrase(base_id):
    if base_id == "tubular_generic":
        return random.choice(tub_core_phrases["tubular_generic"])

    elif base_id in tub_modifier_phrases:
        base = random.choice(tub_core_phrases["tubular_generic"])
        modifier = random.choice(tub_modifier_phrases[base_id])
        return f"{base} {modifier}"

    else:
        raise ValueError(f"Unknown base_id: {base_id}")
    

def get_shape_phrase(base_id):
    if base_id.startswith("cellular"):
        return generate_cell_phrase(base_id)
    elif base_id.startswith("helical"):
        return generate_hel_phrase(base_id)
    elif base_id.startswith("tubular"):
        if base_id == "tubular_shapesize":
            return generate_tub_phrase("tubular_generic")
        return generate_tub_phrase(base_id)
    else:
        raise ValueError(f"Unrecognized base_id: {base_id}")
    


import csv
import json
import random
import re
from pathlib import Path
from typing import Literal, Optional

from scripts.inputgen import get_shape_phrase, generate_input


_STEP_PHRASES = [
    " Think step by step.",
    " think step by step.",
    " think step by step",
    " Think step by step",
]


def strip_code_fences(code: str) -> str:
    """
    Remove surrounding ``` or ```python fences if present.
    Keeps inner code untouched.
    """
    if not code:
        return code

    code = code.strip()

    # ```python ... ```
    m = re.match(r"^```(?:python)?\s*\n(.*)\n```$", code, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # fallback: if it starts with ``` just remove leading/trailing fences naïvely
    if code.startswith("```"):
        code = code.strip("`").strip()
        if code.lower().startswith("python"):
            code = code[len("python"):].strip()
        return code

    return code


def jsonl_to_prompt_csv(
    *,
    jsonl_path: str,
    csv_output_path: str,
    mode: Literal["diverse", "reason", "general"] = "diverse",
    seed: Optional[int] = None,
) -> int:
    """
    Convert a QC'd JSONL into a CSV with columns [prompt, answer].

    Modes:
      - diverse: prompt = generate_input(get_shape_phrase(base_id))
      - reason:  same as diverse + random step-by-step suffix
      - general:     prompt = item["core_prompt"], code = item["code"] with fence stripping

    Returns number of rows written.
    """
    if seed is not None:
        random.seed(seed)

    in_path = Path(jsonl_path)
    out_path = Path(csv_output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0

    with open(in_path, "r", encoding="utf-8") as f_in, open(out_path, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=["prompt", "answer"])
        writer.writeheader()

        for line_num, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
            except Exception:
                continue

            try:
                if mode in ("diverse", "reason"):
                    base_id = (item.get("base_id") or "").strip()
                    code = (item.get("code") or "").strip()
                    if not base_id or not code:
                        continue

                    shape = get_shape_phrase(base_id)
                    prompt = generate_input(shape)
                    if mode == "reason":
                        prompt = prompt + random.choice(_STEP_PHRASES)

                    writer.writerow({"prompt": prompt, "answer": code})
                    rows_written += 1

                elif mode == "general":
                    prompt = (item.get("core_prompt") or "").strip()
                    code = strip_code_fences((item.get("code") or "").strip())
                    if not prompt or not code:
                        continue

                    writer.writerow({"prompt": prompt, "answer": code})
                    rows_written += 1

                else:
                    raise ValueError(f"Unknown mode: {mode}")

            except Exception as e:
                # keep going, but make debugging possible
                print(f"Skipping line {line_num}: {e}")

    return rows_written