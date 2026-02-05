import re
import json

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