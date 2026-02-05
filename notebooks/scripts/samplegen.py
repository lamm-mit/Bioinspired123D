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
