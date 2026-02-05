import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import os
import pandas as pd

def load_finetuned_model(base_model_path: str, fine_tuned_model_path: str):
    """Load the fine-tuned LLM model and tokenizer."""
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model_path, device_map="auto")
    model = PeftModel.from_pretrained(model, fine_tuned_model_path, device_map="auto")
    model.eval()

    return model, tokenizer

def format_input(prompt):
    """Format input for inference."""
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        "You are a helpful assistant<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )

def generate_response(model, tokenizer, prompt, max_length=4096):
    """Generate response from the fine-tuned model."""
    formatted_prompt = format_input(prompt)
    inputs = tokenizer(formatted_prompt, return_tensors="pt")

    # Move inputs to the correct device for inference
    inputs = {key: value.to(model.device) for key, value in inputs.items()}

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_length=max_length,
            do_sample=True,
            temperature=0.1,
            top_p =  0.9
        )

    decoded_output = tokenizer.decode(output[0], skip_special_tokens=True)

    # Extract only the assistant's response
    assistant_start = decoded_output.find("assistant")
    if assistant_start != -1:
        response = decoded_output[assistant_start + len("assistant"):].strip()
    else:
        response = decoded_output.strip()

    return response

def generate_and_save(model, tokenizer, prompt, output_path):
    """Generate Python script output and save to a text file."""
    response = generate_response(model, tokenizer, prompt)

    if not response:
        print("Warning: No response generated.")
        return None

    # Save to a text file
    with open(output_path, "w") as f:
        f.write(response)

    print(f"Saved output to {output_path}")
    return response

# Paths
prompt_csv_path = "benchmark.csv"  
model_csv_path = "finetuned_modelnames.csv"  
base_model_path = "meta-llama/Llama-3.2-3B-Instruct"
results_output_path = "./inference_results_9-22_final_comp/"
os.makedirs(results_output_path, exist_ok=True)

# Load inference CSVs
df_prompts = pd.read_csv(prompt_csv_path)
df_models = pd.read_csv(model_csv_path)  # Ensure this CSV has columns "filepaths" and "model_name"

# Iterate over each fine-tuned model
for _, model_row in df_models.iterrows():
    fine_tuned_model_path = model_row["filepaths"]
    model_name = model_row["model_name"]

    print(f"Loading model '{model_name}' from {fine_tuned_model_path}...")

    # Load finetuned model and tokenizer
    model, tokenizer = load_finetuned_model(base_model_path, fine_tuned_model_path)

    # Run inference for each prompt
    for _, prompt_row in df_prompts.iterrows():
        prompt = prompt_row["prompt"]
        filename = f"{model_name}_{prompt_row['filename']}.txt"

        generate_and_save(
            model,
            tokenizer,
            prompt,
            output_path=os.path.join(results_output_path, filename)
        )

    # Clear model from memory
    del model
    del tokenizer
    torch.cuda.empty_cache()
    print(f"Cleared model '{model_name}' from memory.\n")
