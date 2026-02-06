import json
import os
from typing import Any, Dict, List
import re


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry["source"] = os.path.basename(path)
                data.append(entry)
            except json.JSONDecodeError:
                print(f"⚠️ Skipping invalid JSONL line in {path}")
    return data

def load_all_jsonls(paths: List[str]) -> List[Dict[str, Any]]:
    combined: List[Dict[str, Any]] = []
    for p in paths or []:
        if os.path.exists(p):
            print(f"📂 Loading: {p}")
            combined.extend(load_jsonl(p))
        else:
            print(f"⚠️ File not found: {p}")
    print(f"✅ Loaded {len(combined)} total entries from {len(paths or [])} files.")
    return combined

def extract_blender_code(model_out: str) -> str:
    matches = list(re.finditer(r"```python\s*(.*?)```", model_out, flags=re.DOTALL))
    if matches:
        return matches[-1].group(1).strip()
    pos = model_out.rfind("import bpy")
    return model_out[pos:].strip() if pos != -1 else model_out.strip()


def clean_blender_code(text: str) -> str:
    if not text:
        return "import bpy"
    code = text.strip()
    code = code.replace("```python", "").replace("```", "")
    code = re.sub(r"[\x00-\x08\x0b-\x1f]", "", code)
    if not code.lstrip().startswith("import bpy"):
        code = "import bpy\n" + code
    return code

def extract_assistant_text(text: str) -> str:
    if not text:
        return ""

    # Case 1: token markers
    marker = "<|start_header_id|>assistant<|end_header_id|>"
    if marker in text:
        return text.split(marker, 1)[-1].strip()

    # Case 2: literal "assistant" header (often after skip_special_tokens=True)
    m = re.search(r"(?im)^\s*assistant\s*$", text)
    if m:
        return text[m.end():].strip()

    return text.strip()