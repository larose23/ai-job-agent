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

    # Handle keywords - only expand role categories when explicitly referenced
    if "keywords" in resolved:
        flattened_keywords = []
        for keyword in resolved["keywords"]:
            if isinstance(keyword, str) and keyword.startswith("${role_categories.") and keyword.endswith("}"):
                # This is an explicit reference to a role category
                key_path = keyword[2:-1].split(".")
                ref = resolved
                for k in key_path:
                    ref = ref.get(k, {})
                if isinstance(ref, list):
                    flattened_keywords.extend(ref)
            else:
                # This is an explicit keyword, keep it as is
                flattened_keywords.append(keyword)
        resolved["keywords"] = flattened_keywords

    with open(OUTPUT_FILE, "w") as f:
        json.dump(resolved, f, indent=2)

    print(f"✅ Generated config: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_config()