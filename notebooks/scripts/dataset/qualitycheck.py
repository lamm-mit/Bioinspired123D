import os
import json
import subprocess
import re

def get_validation_template(add_ground_plane=True):
    ground_plane_code = (
        "        bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))\n"
        if add_ground_plane else ""
    )
    return f""" 
import bpy
import os
import sys

try:
    exec(open(r"{{script_path}}").read())

    obj_count = len(bpy.data.objects)
    validation_status = "VALIDATION: Success - Objects Created" if obj_count > 0 else "VALIDATION: Failed - No Objects Created"
    print(validation_status)

    if obj_count > 0:
{ground_plane_code}
        if bpy.context.scene.world is None:
            bpy.context.scene.world = bpy.data.worlds.new("NewWorld")
        bpy.context.scene.world.use_nodes = True
        node_tree = bpy.context.scene.world.node_tree
        bg_node = node_tree.nodes.get("Background") or node_tree.nodes.new(type="ShaderNodeBackground")
        node_tree.links.new(bg_node.outputs[0], node_tree.nodes["World Output"].inputs[0])
        bg_node.inputs[0].default_value = (0.1, 0.1, 0.1, 1)

        if not any(obj.type == "LIGHT" for obj in bpy.data.objects):
            bpy.ops.object.light_add(type='AREA', location=(0, 0, 15))
            light = bpy.context.object
            light.data.energy = 700
            light.data.size = 12

        def get_scene_center():
            objs = [obj for obj in bpy.data.objects if obj.type == 'MESH']
            if not objs:
                return (0, 0, 0)
            min_x = min(obj.bound_box[0][0] + obj.location.x for obj in objs)
            max_x = max(obj.bound_box[6][0] + obj.location.x for obj in objs)
            min_y = min(obj.bound_box[0][1] + obj.location.y for obj in objs)
            max_y = max(obj.bound_box[6][1] + obj.location.y for obj in objs)
            min_z = min(obj.bound_box[0][2] + obj.location.z for obj in objs)
            max_z = max(obj.bound_box[6][2] + obj.location.z for obj in objs)
            return ((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2)

        center = get_scene_center()

        if "Camera" not in bpy.data.objects:
            bpy.ops.object.camera_add(location=(center[0] + 8, center[1] - 8, center[2] + 6))
            cam = bpy.context.object
        else:
            cam = bpy.data.objects["Camera"]
        cam.data.type = 'PERSP'
        cam.rotation_mode = 'XYZ'
        cam.rotation_euler = (1.2, 0, 0.8)

        if not any(c.type == 'TRACK_TO' for c in cam.constraints):
            constraint = cam.constraints.new(type='TRACK_TO')
            target = bpy.data.objects.new("SceneCenter", None)
            target.location = center
            bpy.context.scene.collection.objects.link(target)
            constraint.target = target
            constraint.track_axis = 'TRACK_NEGATIVE_Z'
            constraint.up_axis = 'UP_Y'

        bpy.context.scene.camera = cam
        bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
        bpy.context.scene.eevee.taa_render_samples = 64
        bpy.context.scene.render.resolution_x = 1280
        bpy.context.scene.render.resolution_y = 720

        render_folder = r"{{render_folder}}"
        os.makedirs(render_folder, exist_ok=True)
        bpy.context.scene.render.filepath = os.path.join(render_folder, "{{render_filename}}")
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(write_still=True)
        print(f"Render saved at {{render_folder}}/{{render_filename}}")

except Exception as e:
    print("VALIDATION: Failed - Error:", str(e))
"""


# === Helpers ===


import os, re, json

def sanitize_filename(name: str) -> str:
    # Simple safe filename
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

import os, re, json

def sanitize_filename(name: str) -> str:
    # Simple safe filename
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def extract_scripts_from_jsonl(jsonl_paths, output_folder, debug=True):
    os.makedirs(output_folder, exist_ok=True)
    script_paths = []

    for jsonl_path in jsonl_paths:
        if debug:
            print(f"\n📂 Processing file: {jsonl_path}")
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                try:
                    item = json.loads(line)
                    if debug:
                        print(f"\n--- Line {i} ---")
                        print(f"Keys: {list(item.keys())}")

                    # Handle code source
                    raw_code = item.get("code") or item.get("reasoned", "")
                    if not raw_code:
                        if debug:
                            print("⚠️  No 'code' or 'reasoned' field found, skipping.")
                        continue

                    # Prefer variant_id as filename
                    if "variant_id" in item:
                        filename_base = sanitize_filename(str(item["variant_id"]))
                        if debug:
                            print(f"✅ Using variant_id as filename: {filename_base}")
                    elif "description" in item:
                        filename_base = sanitize_filename(item["description"])
                        if debug:
                            print(f"✅ Using description as filename: {filename_base}")
                    elif "des" in item:
                        filename_base = sanitize_filename(item["des"])
                        if debug:
                            print(f"✅ Using des as filename: {filename_base}")
                    else:
                        filename_base = f"script_{i}"
                        if debug:
                            print(f"⚠️  No variant_id/description, using fallback: {filename_base}")

                    # Match ```python ... ```, ``` ... ```, or '''python ... '''
                    # Match fenced blocks if present
                    blocks = (
                        re.findall(r"```python\s*(.*?)```", raw_code, re.DOTALL)
                        or re.findall(r"```(.*?)```", raw_code, re.DOTALL)
                        or re.findall(r"'''python\s*(.*?)'''", raw_code, re.DOTALL)
                    )

                    if blocks:
                        last_block = blocks[-1].strip()
                    else:
                        last_block = raw_code.strip()
                        if debug:
                            print("⚠️ No fenced block found, using raw 'code' field directly.")
                    last_block = last_block.replace("{{'PARTICLE_OWN'}}", "{'PARTICLE_OWN'}")
                    script_path = os.path.join(output_folder, f"{filename_base}.py")
                    with open(script_path, "w", encoding="utf-8") as out:
                        out.write(last_block)
                    script_paths.append(script_path)

                    if debug:
                        print(f"💾 Extracted script saved to: {script_path}")


                except Exception as e:
                    print(f"❌ Error in {jsonl_path}, line {i}: {e}")

    if debug:
        print(f"\n✅ Done. Extracted {len(script_paths)} scripts total.")
    return script_paths







def create_validation_script(script_path, render_folder, add_ground_plane):
    
    render_filename = os.path.basename(script_path).replace(".py", ".png")
    script_content = get_validation_template(add_ground_plane).format(
        script_path=script_path,
        render_folder=render_folder,
        render_filename=render_filename
    )
    validation_script_path = script_path.replace(".py", "_validate.py")
    with open(validation_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    return validation_script_path

def wsl_to_windows_path(wsl_path):
    result = subprocess.run(["wslpath", "-w", wsl_path], capture_output=True, text=True)
    return result.stdout.strip()

def run_validation_pipeline(script_paths, blender_path, render_folder, add_ground_plane, log_file="blender_validation_log.txt"):
    os.makedirs(render_folder, exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as log:
        for script_path in script_paths:
            val_script = create_validation_script(script_path, render_folder, add_ground_plane)
            win_path = wsl_to_windows_path(val_script)
            print(f"▶ Running Blender on {script_path}...")

            try:
                result = subprocess.run(
                    [blender_path, "--background", "--python", win_path],
                    capture_output=True,
                    text=True
                )
                log.write(f"{script_path}:\n{result.stdout}\n\n")
                print(result.stdout)
            except Exception as e:
                log.write(f"{script_path}:\nError: {str(e)}\n\n")
                print(f"❌ Blender error: {e}")

    print(f"✅ Validation complete. Log: {log_file}")


################################################################################################
def parse_validation_log(log_path):
    """
    Parses a validation log and returns three sets:
    - valid: scripts that passed
    - failed: scripts that failed validation
    - unclassified: scripts where no classification could be determined
    """
    valid = set()
    failed = set()
    unclassified = set()

    current_script = None
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Detect new script block
            if line.endswith(".py:"):
                current_script = line[:-1]  # remove colon
                continue

            # Check for validation status
            if "VALIDATION:" in line and current_script:
                if "Failed" in line:
                    failed.add(current_script)
                elif "Success" in line:
                    valid.add(current_script)
                else:
                    unclassified.add(current_script)
                current_script = None  # reset after classification

    print(f"✅ Valid: {len(valid)}, ❌ Failed: {len(failed)}, ❓ Unclassified: {len(unclassified)}")
    return valid, failed, unclassified


import os
import json

def filter_jsonl_by_validation(input_jsonl_path, log_path, output_jsonl_path):
    """
    Filter out failed/unclassified entries from a JSONL dataset based on validation log.
    Assumes parse_validation_log(log_path) returns (valid, failed, unclassified), where each entry is a path like:
    'blender_scripts/cube_with_cylinder_cut_v0.py'
    """

    # Import your existing log parser
    valid, failed, unclassified = parse_validation_log(log_path)
    scripts_to_remove = failed.union(unclassified)

    # Extract clean base names like 'cube_with_cylinder_cut_v0'
    filename_bases_to_remove = set()
    for script_path in scripts_to_remove:
        if script_path.endswith(".py"):
            base = os.path.splitext(os.path.basename(script_path))[0]
            filename_bases_to_remove.add(base.strip().lower())

    print(f"🛑 Will remove {len(filename_bases_to_remove)} scripts: {sorted(filename_bases_to_remove)}")

    # Filter JSONL entries
    filtered_entries = []
    removed_count = 0

    with open(input_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            variant_id = item.get("variant_id", "").strip().lower()

            if variant_id not in filename_bases_to_remove:
                filtered_entries.append(line)
            else:
                removed_count += 1

    # Write filtered file
    with open(output_jsonl_path, "w", encoding="utf-8") as f:
        f.writelines(filtered_entries)

    print(f"🧹 Removed {removed_count} failed/unclassified entries.")
    print(f"📄 Saved filtered JSONL to: {output_jsonl_path}")
    return removed_count



import os
import json

def filter_jsonl_by_renders(delete_folder, input_jsonl_path, output_jsonl_path):
    """Remove entries from a JSONL file if their render image is in the 'delete' folder."""

    # Step 1: Get filename_bases from images to delete
    filename_bases_to_remove = {
        os.path.splitext(fname)[0]
        for fname in os.listdir(delete_folder)
        if fname.endswith(".png")
    }

    print(f"🗑️ Found {len(filename_bases_to_remove)} images marked for deletion.")

    # Step 2: Filter JSONL
    filtered_entries = []
    removed_count = 0

    with open(input_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            filename_base = item.get("variant_id", "")
            if filename_base not in filename_bases_to_remove:
                filtered_entries.append(line)
            else:
                removed_count += 1

    # Step 3: Save filtered JSONL
    with open(output_jsonl_path, "w", encoding="utf-8") as f:
        f.writelines(filtered_entries)

    print(f"\n✅ Removed {removed_count} entries.")
    print(f"📄 Saved final JSONL to: {output_jsonl_path}")

