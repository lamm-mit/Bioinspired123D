from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import os, re, subprocess, shutil, time
from datetime import datetime

@dataclass
class BlenderExecConfig:
    blender_path: str
    win_render_base: str
    wsl_render_base: str
    tmp_dir_wsl: str = "/mnt/c/Users/Rachel/bio3d_tmp"
    timeout_s: int = 300
    cleanup: bool = True

def to_windows_path(wsl_path: str) -> str:
    if wsl_path.startswith("/mnt/"):
        drive = wsl_path[5].upper()
        win_path = wsl_path.replace(f"/mnt/{wsl_path[5]}/", f"{drive}:/")
        return win_path.replace("/", "\\")
    return wsl_path

VALIDATION_TEMPLATE = """
import bpy, os, sys, random
try:
    code = open(r"{script_path}").read()
    exec(code)
    obj_count = len(bpy.data.objects)
    print(f"Objects in scene: {{obj_count}}")
    if obj_count == 0:
        print("VALIDATION: Failed - No Objects Created")
        sys.exit(1)

    mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
    random.seed(0)
    shades = [i / max(1, len(mesh_objs) - 1) for i in range(len(mesh_objs))]
    for i, (obj, shade) in enumerate(zip(mesh_objs, shades)):
        mat = bpy.data.materials.new(name=f"AutoGray_{{i}}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            base = shade * 0.6 + 0.2
            tint = random.uniform(-0.05, 0.05)
            r = min(max(base + tint, 0), 1)
            g = min(max(base + tint/2, 0), 1)
            b = min(max(base - tint, 0), 1)
            bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
            bsdf.inputs["Specular IOR Level"].default_value = 0.25
            bsdf.inputs["Roughness"].default_value = 0.4
        obj.active_material = mat

    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("NewWorld")
    bpy.context.scene.world.use_nodes = True
    node_tree = bpy.context.scene.world.node_tree
    bg_node = node_tree.nodes.get("Background") or node_tree.nodes.new(type="ShaderNodeBackground")
    node_tree.links.new(bg_node.outputs[0], node_tree.nodes["World Output"].inputs[0])
    bg_node.inputs[0].default_value = (0.05, 0.05, 0.05, 1)

    if not any(o.type == 'LIGHT' for o in bpy.data.objects):
        bpy.ops.object.light_add(type='AREA', location=(0, 0, 15))
        light = bpy.context.object
        light.data.energy = 800
        light.data.size = 14

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
        return ((min_x + max_x)/2, (min_y + max_y)/2, (min_z + max_z)/2)

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
    os.makedirs(r"{render_folder}", exist_ok=True)
    bpy.context.scene.render.filepath = os.path.join(r"{render_folder}", "{render_filename}")
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print(f"Render saved at {{bpy.context.scene.render.filepath}}")
    print("VALIDATION: Success - Render complete")
except Exception as e:
    print("VALIDATION: Failed - Error:", str(e))
    import traceback; traceback.print_exc(); sys.exit(1)
"""


class BlenderValidator:
    def __init__(self, cfg: BlenderExecConfig):
        self.cfg = cfg
        os.makedirs(cfg.wsl_render_base, exist_ok=True)

    def run(self, code_str: str, label: str = "test", render_subdir_wsl: Optional[str] = None) -> Dict[str, str]:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cfg = self.cfg

        render_root_win = cfg.win_render_base

        if render_subdir_wsl:
            render_subdir_wsl = os.path.abspath(render_subdir_wsl)
            ts_folder = os.path.basename(render_subdir_wsl.rstrip("/"))
            render_subdir_win = os.path.join(render_root_win, ts_folder)
        else:
            render_subdir_wsl = os.path.join(cfg.wsl_render_base, ts)
            render_subdir_win = os.path.join(render_root_win, ts)

        os.makedirs(cfg.tmp_dir_wsl, exist_ok=True)
        os.makedirs(render_subdir_wsl, exist_ok=True)
        os.makedirs(render_subdir_win, exist_ok=True)

        script_path_wsl = os.path.join(cfg.tmp_dir_wsl, f"{label}.py")
        validator_path_wsl = os.path.join(cfg.tmp_dir_wsl, f"{label}_validate.py")
        render_file = f"render_{label}.png"

        with open(script_path_wsl, "w", encoding="utf-8") as f:
            f.write(code_str)

        saved_code_path = os.path.join(render_subdir_wsl, f"{label}_generated.py")
        with open(saved_code_path, "w", encoding="utf-8") as f:
            f.write(code_str)

        with open(validator_path_wsl, "w", encoding="utf-8") as f:
            f.write(VALIDATION_TEMPLATE.format(
                script_path=to_windows_path(script_path_wsl),
                render_folder=render_subdir_win,
                render_filename=render_file
            ))

        print(f"▶️ Running Blender Headless... [{ts}]")
        validator_path_win = to_windows_path(validator_path_wsl)

        result = subprocess.run(
            [cfg.blender_path, "-b", "--python", validator_path_win],
            capture_output=True, text=True, timeout=cfg.timeout_s
        )

        stdout, stderr = result.stdout, result.stderr
        status = "success" if "VALIDATION: Success" in stdout else "failed"

        err_snippet = ""
        if status != "success":
            m = re.search(r"VALIDATION:\s*Failed\s*-\s*Error:(.*?)(?:VALIDATION:|Blender quit|$)", stdout, re.S)
            if m:
                err_snippet = "\n".join(m.group(1).strip().splitlines()[:15])
            else:
                lines = stdout.splitlines()[-20:] or stderr.splitlines()[-20:]
                err_snippet = "\n".join(lines).strip()

        wsl_render_file = os.path.join(
            "/mnt/c/Users/Rachel/bio3d_tmp/renders",
            os.path.basename(render_subdir_win),
            render_file
        )
        dest_render_file = os.path.join(render_subdir_wsl, render_file)

        for _ in range(5):
            if os.path.exists(wsl_render_file):
                shutil.copy2(wsl_render_file, dest_render_file)
                break
            time.sleep(1)

        if cfg.cleanup:
            for fpath in [script_path_wsl, validator_path_wsl]:
                try:
                    if os.path.exists(fpath):
                        os.remove(fpath)
                except Exception as e:
                    print(f"⚠️ Cleanup error: {e}")

        return {
            "success": str(status == "success"),
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
            "render_path": dest_render_file,
            "error_snippet": err_snippet,
        }
