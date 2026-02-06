from __future__ import annotations
import re
import json
import os
from typing import Iterable, Set

def query_llm(prompt: str, client, model, temperature: float = 0.1) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return completion.choices[0].message.content.strip()

def extract_json_block(text):
    # Try to extract the first full JSON array from the response
    match = re.search(r'\[\s*{.*?}\s*]', text, re.DOTALL)
    if not match:
        raise ValueError("No valid JSON array found in response")
    return json.loads(match.group(0))

def save_variants_to_jsonl(variants, filepath):
    with open(filepath, 'a', encoding='utf-8') as f:
        for variant in variants:
            json.dump(variant, f)
            f.write('\n')

def load_variants_from_jsonl(filepath):
    variants = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            variant = {
                "code": data["code"],
                "des": data["des"],
                "variant_id": data["variant_id"],
                "changes":data["changes"],
                "base_id": data["base_id"]
            }
            variants.append(variant)
    return variants


def get_keep_ids_from_folder(folder: str, ext: str = ".png") -> Set[str]:
    return {
        os.path.splitext(f)[0]
        for f in os.listdir(folder)
        if f.endswith(ext)
    }


def filter_jsonl_by_ids(input_jsonl: str, output_jsonl: str, keep_ids: Set[str], id_key: str = "id") -> int:
    kept = 0
    with open(input_jsonl, "r", encoding="utf-8") as infile, open(output_jsonl, "w", encoding="utf-8") as outfile:
        for line in infile:
            entry = json.loads(line)
            if entry.get(id_key) in keep_ids:
                outfile.write(json.dumps(entry) + "\n")
                kept += 1
    return kept
