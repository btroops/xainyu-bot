import os

def load_prompt(name: str) -> str:
    custom = f"prompts/{name}.txt"
    example = f"prompts/{name}_example.txt"
    if os.path.exists(custom):
        with open(custom, "r", encoding="utf-8") as f:
            return f.read()
    with open(example, "r", encoding="utf-8") as f:
        return f.read()