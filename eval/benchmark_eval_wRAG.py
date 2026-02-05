import os
import re
import json
import faiss
import torch
import numpy as np
import pandas as pd
from peft import PeftModel
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM

# ============================
# 1. Load JSONL base codes
# ============================
def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


# ============================
# 2. Embedding model (for retrieval)
# ============================
def build_index(jsonl_path):
    base_codes = load_jsonl(jsonl_path)
    embed_model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    def get_embedding(item):
        text = item["instruction"] + "\n" + item["code"]
        return embed_model.encode(text, normalize_embeddings=True)

    embeddings = np.vstack([get_embedding(item) for item in base_codes]).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])  # cosine similarity
    index.add(embeddings)

    print(f"✅ Indexed {len(base_codes)} base items.")
    return base_codes, embed_model, index


def retrieve(query, k, embed_model, index, base_codes):
    q_emb = embed_model.encode([query], normalize_embeddings=True).astype("float32")
    D, I = index.search(q_emb, k)
    results = []
    for rank, idx in enumerate(I[0]):
        item = base_codes[idx]
        results.append({
            "rank": rank,
            "score": float(D[0][rank]),
            "category": item["category"],
            "instruction": item["instruction"],
            "code": item["code"]
        })
    return results


def build_context(query, embed_model, index, base_codes, k=3):
    retrieved = retrieve(query, k, embed_model, index, base_codes)
    context = []
    for r in retrieved:
        context.append(
            f"Instruction: {r['instruction']}\n"
            f"Category: {r['category']}\n"
            f"Code:\n{r['code']}\n"
        )
    return "\n---\n".join(context)


# ============================
# 3. Finetuned LLM
# ============================
def load_finetuned_model(base_model_path: str, fine_tuned_model_path: str):
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model_path, device_map="auto")
    model = PeftModel.from_pretrained(model, fine_tuned_model_path, device_map="auto")
    model.eval()
    return model, tokenizer


def format_input(prompt):
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        "You are a helpful assistant<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{prompt}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def generate_response(model, tokenizer, prompt, max_new_tokens=4096):
    formatted_prompt = format_input(prompt)
    inputs = tokenizer(formatted_prompt, return_tensors="pt")
    inputs = {key: value.to(model.device) for key, value in inputs.items()}

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.1,
            top_p=0.9
        )

    decoded_output = tokenizer.decode(output[0], skip_special_tokens=True)

    # Extract only assistant's part
    assistant_start = decoded_output.find("assistant")
    if assistant_start != -1:
        response = decoded_output[assistant_start + len("assistant"):].strip()
    else:
        response = decoded_output.strip()

    return response


# ============================
# 4. Prompt builder
# ============================
def build_prompt(query, context_block):
    return f"""You are a Blender scripting assistant.

Here are some useful base codes retrieved from the database:

{context_block}

User request: {query}

Generate ONLY valid Blender Python code.
"""


# ============================
# 5. Code extraction (optional)
# ============================
def extract_code(text):
    match = re.search(r"```python(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


# ============================
# 6. Main script
# ============================
if __name__ == "__main__":
    # ---- Paths ----
    jsonl_path = "biodataset_baserag.jsonl"
    csv_path = "benchmark.csv"  # CSV with columns: prompt, filename
    output_folder = "llm_wrag_10-8_stress"

    os.makedirs(output_folder, exist_ok=True)

    # ---- Load retriever ----
    base_codes, embed_model, index = build_index(jsonl_path)

    # ---- Load finetuned model ----
    base_model_path = "meta-llama/Llama-3.2-3B-Instruct"
    fine_tuned_model_path = "./llama_finetuned_blender_9-22/checkpoint-500"
    llm_model, llm_tokenizer = load_finetuned_model(base_model_path, fine_tuned_model_path)

    # ---- Load prompts ----
    df = pd.read_csv(csv_path)
    print(f"🧠 Loaded {len(df)} prompts from {csv_path}")

    # ---- Run inference ----
    for _, row in df.iterrows():
        query = row["prompt"]
        filename = str(row["filename"]).strip()
        print(f"\n🚀 Running query: {query}")

        try:
            # Retrieve + build context
            context_block = build_context(query, embed_model, index, base_codes, k=2)
            prompt = build_prompt(query, context_block)

            # Generate response
            raw_response = generate_response(llm_model, llm_tokenizer, prompt)

            # Save raw response
            output_path = os.path.join(output_folder, f"{filename}.txt")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(raw_response)

            print(f"✅ Saved response to {output_path}")

        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
