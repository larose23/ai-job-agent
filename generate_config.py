import os
import json
import re
from dotenv import load_dotenv

TEMPLATE_FILE = "config.json.template"
OUTPUT_FILE = "config.json"

def resolve_placeholders(obj, env_vars):
    if isinstance(obj, dict):
        return {k: resolve_placeholders(v, env_vars) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_placeholders(v, env_vars) for v in obj]
    elif isinstance(obj, str):
        matches = re.findall(r"\${(.*?)}", obj)
        for match in matches:
            replacement = env_vars.get(match)
            if replacement:
                obj = obj.replace(f"${{{match}}}", replacement)
        return obj
    else:
        return obj

def generate_config():
    load_dotenv()

    with open(TEMPLATE_FILE, "r") as f:
        template = json.load(f)

    env_vars = dict(os.environ)
    resolved = resolve_placeholders(template, env_vars)

    # Also flatten role_categories into keywords list if needed
    if "keywords" in resolved:
        flattened_keywords = []
        for group in resolved["keywords"]:
            if isinstance(group, list):
                flattened_keywords.extend(group)
            elif isinstance(group, str) and group.startswith("${") and group.endswith("}"):
                key_path = group[2:-1].split(".")
                ref = resolved
                for k in key_path:
                    ref = ref.get(k, {})
                if isinstance(ref, list):
                    flattened_keywords.extend(ref)
        resolved["keywords"] = flattened_keywords

    with open(OUTPUT_FILE, "w") as f:
        json.dump(resolved, f, indent=2)

    print(f"✅ Generated config: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_config()
