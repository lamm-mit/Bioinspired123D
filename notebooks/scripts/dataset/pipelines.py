from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional, List

import pandas as pd

from scripts.llm_utils import query_llm, extract_json_block, save_variants_to_jsonl, load_variants_from_jsonl
from scripts.prompting import build_diversify_prompt, build_reasoning_prompt


@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.25
    sleep_s: float = 2.0


def generate_variants_once(
    *,
    client,
    prompt: str,
    base_id: str,
    run_index: int,
    parameters: str,
    des: str,
    output_file: str,
    cfg: LLMConfig,
    expect_changes: bool,
) -> None:
    response_text = query_llm(prompt, client, cfg.model, temperature=cfg.temperature)

    variants = extract_json_block(response_text)  # raises if malformed
    structured = []

    for i, v in enumerate(variants):
        item = {
            "base_id": base_id,
            "run_index": run_index,
            "variant_index": i,
            "variant_id": f"{base_id}_run{run_index}_v{i}",
            "parameters": parameters,
            "code": v["code"],
            "des": des,
        }
        if expect_changes:
            item["changes"] = v.get("changes", "")
        structured.append(item)

    save_variants_to_jsonl(structured, output_file)


def run_diversification(
    *,
    client,
    csv_path: str,
    output_file: str,
    n_variants: int,
    total_runs: int,
    cfg: LLMConfig,
    prompt_kind: str,  
) -> None:
    df = pd.read_csv(csv_path)

    for index, row in df.iterrows():
        base_id = str(row["ID"])
        base_script = row["Code"]
        parameters = row.get("Parameters", "")
        des = row.get("Descript", "")

        print(f"\nGenerating base_id={base_id} ({index + 1}/{len(df)})")

        for run_index in range(total_runs):
            print(f"  Run {run_index + 1}/{total_runs}")

            if prompt_kind == "diverse":
                prompt = build_diversify_prompt(base_script, parameters, n_variants)
                expect_changes = True
            else:
                raise ValueError("prompt_kind must be 'diverse'")

            try:
                generate_variants_once(
                    client=client,
                    prompt=prompt,
                    base_id=base_id,
                    run_index=run_index,
                    parameters=parameters,
                    des=des,
                    output_file=output_file,
                    cfg=cfg,
                    expect_changes=expect_changes,
                )
            except Exception as e:
                print(f"Error on base_id={base_id} run={run_index}: {e}")

            time.sleep(cfg.sleep_s)


def save_reasoned_variants(items: List[Dict[str, Any]], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        for item in items:
            json.dump(item, f)
            f.write("\n")


def run_reasoning_generation(
    *,
    client,
    input_path: str,
    output_path: str,
    reasoning_example_txt_path: str,
    cfg: LLMConfig,
) -> None:
    with open(reasoning_example_txt_path, "r", encoding="utf-8") as f:
        example = f.read()

    variants = load_variants_from_jsonl(input_path)
    results = []

    for v in variants:
        vid = v.get("variant_id", "unknown")
        print(f"Processing {vid}...")

        try:
            prompt = build_reasoning_prompt(v["code"], v.get("des", ""), example)
            reasoned = query_llm(prompt, client, cfg.model, temperature=cfg.temperature)
            results.append(
                {
                    "base_id": v.get("base_id", ""),
                    "variant_id": vid,
                    "code": reasoned,
                }
            )
        except Exception as e:
            print(f"Failed on {vid}: {e}")

        time.sleep(cfg.sleep_s)

    save_reasoned_variants(results, output_path)
    print(f"Saved {len(results)} reasoned variants to {output_path}")




import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional
import json
from datetime import datetime
from .inputgen import generate_input
from .llm_utils import query_llm

def generate_gendataset(tasks, format_hint, output_file, client, n_variants_per_shape=10, temp=0.1, model="gpt-4o-mini"):
    """Generates a dataset and writes it to a JSONL file."""
    with open(output_file, "w") as f:
        entry_index = 0
        for task in tasks:
            for i in range(n_variants_per_shape):
                core_prompt = generate_input(task["shape"])
                full_prompt = f"{core_prompt} {format_hint}"
                try:
                    code = query_llm(full_prompt, client, model, temperature=temp)
                    entry = {
                        "task_name": task["task_name"],
                        "category": task["category"],
                        "core_prompt": core_prompt,
                        "prompt": full_prompt,
                        "code": code,
                        "variant_id": f"{task['task_name']}_v{i}",
                        "model": model,
                        "timestamp": datetime.now().isoformat()
                    }
                    f.write(json.dumps(entry) + "\n")
                    print(f"✓ Saved: {task['task_name']}_v{i}")
                    entry_index += 1

                except Exception as e:
                    print(f"⚠️ Failed: {task['task_name']} — {e}")


DEFAULT_FORMAT_HINT = (
    "Solve the task in the simplest and most straightforward way, using standard Blender operations. "
    "Respond only with a Python code block that starts with:\n\n"
    "```python\n"
    "import bpy\n\n"
    "bpy.ops.object.select_all(action='SELECT')\n"
    "bpy.ops.object.delete(use_global=False)\n\n"
    "[code]\n"
    "```"
)


def get_blender_general_tasks() -> Dict[str, List[dict]]:
    primitive = [
        {"task_name": "make_rectangular_prism", "shape": "a rectangular prism", "category": "primitive"},
        {"task_name": "make_cube", "shape": "a cube", "category": "primitive"},
        {"task_name": "make_sphere", "shape": "a sphere", "category": "primitive"},
        {"task_name": "make_cylinder", "shape": "a cylinder", "category": "primitive"},
        {"task_name": "make_cone", "shape": "a cone", "category": "primitive"},
        {"task_name": "make_hexagonal_prism", "shape": "a hexagonal prism", "category": "primitive"},
    ]

    transform = [
        # rotation
        {"task_name": "rotate_cube_45_degrees", "shape": "a cube and rotate it by 45 degrees around the Z axis", "category": "transform"},
        {"task_name": "lay_cylinder_on_its_side", "shape": "a cylinder and lay it on its side", "category": "transform"},
        {"task_name": "rotate_cone_90_y", "shape": "a cone and rotate it 90 degrees around the Y axis", "category": "transform"},
        {"task_name": "rotate_cube_30_x", "shape": "a cube and rotate it 30 degrees around the X axis", "category": "transform"},
        {"task_name": "upside_down", "shape": "a cone and turn it upside down", "category": "transform"},
        # translation
        {"task_name": "move_sphere_up", "shape": "a sphere and move it upward by 3 units", "category": "transform"},
        {"task_name": "move_cube_to_side", "shape": "a cube and move to the right by 2 units", "category": "transform"},
        {"task_name": "offset_cone_along_x", "shape": "a cone and move along the X axis by 3 units", "category": "transform"},
        {"task_name": "move_cylinder_upward", "shape": "a cylinder and move to location (0, 0, 5)", "category": "transform"},
        {"task_name": "random_cube_positions", "shape": "a cube and place at a random location within 3x3x3 grid", "category": "transform"},
        # scaling
        {"task_name": "scale_cube_uniformly", "shape": "a cube and scale it up by 2x", "category": "transform"},
        {"task_name": "stretch_cylinder_vertically", "shape": "a cylinder and stretch along the Z axis by 2 times", "category": "transform"},
        {"task_name": "flatten_sphere", "shape": "a sphere and flatten along the Z axis to 0.3", "category": "transform"},
        {"task_name": "shrink_cone", "shape": "a cone and scale down by 50%", "category": "transform"},
        {"task_name": "ellipse_cylinder", "shape": "a cylinder and scale in the y direction to make it elliptical", "category": "transform"},
    ]

    advanced = [
        {"task_name": "cube_with_corner_spheres", "shape": "a cube and place small spheres at each of its corners", "category": "advanced"},
        {"task_name": "cube_with_top_hole", "shape": "a cube with a circular hole through the top", "category": "advanced"},
        {"task_name": "stacked_cylinders", "shape": "3 cylinders stacked ontop of one another", "category": "advanced"},
        {"task_name": "cube_on_cube", "shape": "a small cube ontop of a larger cube", "category": "advanced"},
        {"task_name": "ring_of_cubes", "shape": "8 cubes evenly in a circle", "category": "advanced"},
        {"task_name": "grid_of_cylinders", "shape": "a 3x3x3 grid of cylinders", "category": "advanced"},
        {"task_name": "sphere_cutout", "shape": "a sphere with a horizontal cylinder subtracted through its center", "category": "advanced"},
        {"task_name": "hollow_cylinder", "shape": "a hollow cylinder by subtracting a smaller cylinder from the center of a larger one", "category": "advanced"},
        {"task_name": "cone_cylinder", "shape": "a cone ontop of a cylinder", "category": "advanced"},
        {"task_name": "prism_stack", "shape": "a stack of three rectangular prisms", "category": "advanced"},
        {"task_name": "cube_with_sphere_cutouts", "shape": "a cube with small spheres subtracted from each face center", "category": "advanced"},
        {"task_name": "hollow_hexagonal", "shape": "a hollow hexagonal cell by subtracting a smaller hexagonal prism from the center of a larger one", "category": "advanced"},
        {"task_name": "elliptical_cylinders", "shape": "an elliptical cylinder", "category": "advanced"},
        {"task_name": "cube_on_cylinder", "shape": "a cube placed directly on top of a cylinder", "category": "advanced"},
        {"task_name": "circle_of_spheres", "shape": "8 spheres evenly spaced in a circular arrangement", "category": "advanced"},
        {"task_name": "three_cubes_in_a_row", "shape": "three cubes lined up in a straight row", "category": "advanced"},
        {"task_name": "cube_with_cylinder_cut", "shape": "a cylinder subtracted from the top of a cube", "category": "advanced"},
        {"task_name": "cube_with_chamfered_edges", "shape": "a cube with beveled edges", "category": "advanced"},
        {"task_name": "spiral_stack_of_cubes", "shape": "cubes stacked with incremental rotation to form a spiral", "category": "advanced"},
        {"task_name": "stacked_scaled_cubes", "shape": "three cubes stacked with increasing size", "category": "advanced"},
        {"task_name": "cylinder_array_on_circle", "shape": "6 vertical cylinders placed evenly around a circle", "category": "advanced"},
        {"task_name": "random_cubes", "shape": "3 cubes placed in random locations around a 3x3x3 grid", "category": "advanced"},
        {"task_name": "hollow_elliptical", "shape": "a hollow elliptical cylinder by subtracting a smaller elliptical cylinder from the center of a larger one", "category": "advanced"},
        {"task_name": "rotated_cube_grid", "shape": "a 3x3 grid of cubes each rotated slightly in Z", "category": "advanced"},
        {"task_name": "sandwich_cylinder", "shape": "a cylinder sandwiched between a top and bottom rectangular prism", "category": "advanced"},
    ]

    return {"primitive": primitive, "transform": transform, "advanced": advanced}


@dataclass
class GeneralDatasetConfig:
    model: str = "gpt-4o-mini"
    temp: float = 0.1
    format_hint: str = DEFAULT_FORMAT_HINT

    # how many samples per task per category
    n_primitive: int = 25
    n_transform: int = 70
    n_advanced: int = 72

    # output behavior
    output_file: str = "blender_general_dataset_noQC.jsonl"
    write_intermediate_files: bool = False
    delete_intermediates: bool = True


def generate_blender_general_dataset(*, client, cfg: GeneralDatasetConfig) -> str:
    tasks_by_cat = get_blender_general_tasks()

    # Decide outputs
    if cfg.write_intermediate_files:
        prim_out = "blender_primitive_dataset.jsonl"
        trans_out = "blender_transform_dataset.jsonl"
        adv_out = "blender_advanced_dataset.jsonl"
    else:
        # still generate into temp files so we can safely append/merge
        prim_out = "_tmp_blender_primitive.jsonl"
        trans_out = "_tmp_blender_transform.jsonl"
        adv_out = "_tmp_blender_advanced.jsonl"

    # Generate each category
    generate_gendataset(
        tasks=tasks_by_cat["primitive"],
        format_hint=cfg.format_hint,
        output_file=prim_out,
        n_variants_per_shape=cfg.n_primitive,
        temp=cfg.temp,
        model=cfg.model,
        client=client,
    )

    generate_gendataset(
        tasks=tasks_by_cat["transform"],
        format_hint=cfg.format_hint,
        output_file=trans_out,
        n_variants_per_shape=cfg.n_transform,
        temp=cfg.temp,
        model=cfg.model,
        client=client,
    )

    generate_gendataset(
        tasks=tasks_by_cat["advanced"],
        format_hint=cfg.format_hint,
        output_file=adv_out,
        n_variants_per_shape=cfg.n_advanced,
        temp=cfg.temp,
        model=cfg.model,
        client=client,
    )

    # Merge
    input_files = [trans_out, prim_out, adv_out]
    with open(cfg.output_file, "w", encoding="utf-8") as outfile:
        for fpath in input_files:
            with open(fpath, "r", encoding="utf-8") as infile:
                shutil.copyfileobj(infile, outfile)

    # Cleanup
    if cfg.delete_intermediates:
        for fpath in input_files:
            if os.path.exists(fpath):
                os.remove(fpath)

    return cfg.output_file



from pathlib import Path
from typing import List

from scripts.qualitycheck import (
    extract_scripts_from_jsonl,
    run_validation_pipeline,
    filter_jsonl_by_validation,
)


def validate_and_filter_all_processed_jsonl(
    *,
    processed_dir: str = "../data/processed",
    blender_path: str,
    out_root: str = "../data/qc_outputs",
    add_ground_plane: bool = False,
    debug_extract: bool = True,
) -> List[str]:
    """
    For every .jsonl in processed_dir:
      - extract scripts
      - run Blender validation
      - filter JSONL based on validation log

    Produces per-file outputs:
      <name>_scripts/
      <name>_renders/
      <name>.log.txt
      <name>_filtered.jsonl

    Returns list of filtered JSONL paths.
    """
    processed_path = Path(processed_dir)
    if not processed_path.exists():
        raise FileNotFoundError(f"processed_dir not found: {processed_path.resolve()}")

    out_root_path = Path(out_root)
    out_root_path.mkdir(parents=True, exist_ok=True)

    jsonl_files = sorted(processed_path.glob("*.jsonl"))
    if not jsonl_files:
        print(f"No .jsonl files found in {processed_path.resolve()}")
        return []

    filtered_outputs = []

    for jsonl_path in jsonl_files:
        stem = jsonl_path.stem

        script_output_folder = out_root_path / f"{stem}_scripts"
        render_output_folder = out_root_path / f"{stem}_renders"
        log_file = out_root_path / f"{stem}.log.txt"
        filtered_jsonl = out_root_path / f"{stem}_filtered.jsonl"

        script_output_folder.mkdir(parents=True, exist_ok=True)
        render_output_folder.mkdir(parents=True, exist_ok=True)

        print(f"\n=== QC + FILTER for: {jsonl_path.name} ===")
        print(f"scripts  -> {script_output_folder}")
        print(f"renders  -> {render_output_folder}")
        print(f"log      -> {log_file}")
        print(f"filtered -> {filtered_jsonl}")

        # 1) Extract scripts
        scripts = extract_scripts_from_jsonl(
            jsonl_paths=[str(jsonl_path)],
            output_folder=str(script_output_folder),
            debug=debug_extract,
        )

        # 2) Run Blender validation
        run_validation_pipeline(
            script_paths=scripts,
            blender_path=blender_path,
            render_folder=str(render_output_folder),
            add_ground_plane=add_ground_plane,
            log_file=str(log_file),
        )

        # 3) Filter JSONL using validation log
        filter_jsonl_by_validation(
            input_jsonl_path=str(jsonl_path),
            log_path=str(log_file),
            output_jsonl_path=str(filtered_jsonl),
        )

        filtered_outputs.append(str(filtered_jsonl))

    return filtered_outputs
