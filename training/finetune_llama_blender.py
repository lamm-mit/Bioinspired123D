import torch
from transformers import AutoTokenizer
from torch.utils.data import Dataset
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model
import os
from huggingface_hub import login

login(token=os.environ["HUGGINGFACE_TOKEN"])

from transformers import DataCollatorForSeq2Seq

class SmartCollator(DataCollatorForSeq2Seq):
    def __call__(self, features):
        batch = super().__call__(features)
        device = batch["input_ids"].device
        batch["labels"] = batch["labels"].to(device)
        return batch

if torch.cuda.is_available():
    print(f"CUDA is available. Number of GPUs: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
else:
    print("CUDA is not available.")

class SFTDataset(Dataset):
    def __init__(self, csv_file, tokenizer, max_length=2048):
        self.data = pd.read_csv(csv_file)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        prompt = row["prompt"]
        response = row["answer"]

        formatted_input = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            "You are a helpful assistant<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
            f"{response}<|eot_id|>"
        )

        sep = "<|start_header_id|>assistant<|end_header_id|>\n\n"
        response_start = formatted_input.find(sep) + len(sep)

        tok = self.tokenizer(
            formatted_input,
            truncation=True,
            max_length=self.max_length,
            padding=False,
            return_tensors=None,    
        )

        input_ids = tok["input_ids"]
        attention_mask = tok["attention_mask"]

        # mask labels before assistant response
        resp_tok_start = len(
            self.tokenizer.encode(
                formatted_input[:response_start],
                add_special_tokens=False
            )
        )

        labels = input_ids.copy()
        for i in range(resp_tok_start):
            labels[i] = -100

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels
        }


 
# Model and Tokenizer loading
model_name ="meta-llama/Llama-3.2-3B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


model = AutoModelForCausalLM.from_pretrained(model_name)
model.config.use_cache = False
model.resize_token_embeddings(len(tokenizer))
model.gradient_checkpointing_enable()

# Setup LoRA configuration
lora_config = LoraConfig(
    r=64,
    lora_alpha=64,
    target_modules=["q_proj", "v_proj", "k_proj","o_proj",'gate_proj', 'down_proj', 'up_proj'],  
    lora_dropout=0.1,
    bias="none",
)
model = get_peft_model(model, lora_config)
print("Trainable parameters:")
model.print_trainable_parameters()

# Prepare the dataset
train_dataset = SFTDataset("bioinspired3d_dataset_final.csv", tokenizer)

# Training arguments
training_args = TrainingArguments(
    output_dir="./llama_finetuned_blender/",
    num_train_epochs=4,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    learning_rate=1e-4,
    warmup_steps = 50,
    logging_steps=10,
    save_steps=100,
    fp16=True,
    remove_unused_columns=False
)

collator = SmartCollator(tokenizer=tokenizer, model=model)

# Trainer setup
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    data_collator = collator,
)

# Start training
trainer.train()
