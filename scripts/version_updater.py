import json
import re

version_info_file = "../version.json"
with open(version_info_file) as f:
    version = json.load(f)["version"]

readme_md_path = "../README.md"
with open(readme_md_path, "r", encoding="utf-8") as f:
    content = f.read()
new_content = re.sub(r"Version: \d+\.\d+\.\d+", f"Version: {version}", content)
with open(readme_md_path, "w", encoding="utf-8") as f:
    f.write(new_content)

server_config_path = "../server/server_config.json"
with open(server_config_path, "r", encoding="utf-8") as f:
    content = f.read()
new_content = re.sub(
    r"\"version\": \"\d+\.\d+\.\d+\"", f"\"version\": \"{version}\"", content
)
with open(server_config_path, "w", encoding="utf-8") as f:
    f.write(new_content)

server_config_path = "../client/client_config.json"
with open(server_config_path, "r", encoding="utf-8") as f:
    content = f.read()
new_content = re.sub(
    r"\"version\": \"\d+\.\d+\.\d+\"", f"\"version\": \"{version}\"", content
)
with open(server_config_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Version update completed.")
