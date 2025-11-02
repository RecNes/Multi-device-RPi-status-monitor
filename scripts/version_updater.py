"""Script to update version numbers in multiple files based on version.json."""
import json
import re
import os


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
version_info_file = os.path.join(base_dir, "version.json")
readme_md_path = os.path.join(base_dir, "README.md")
server_dir = os.path.join(base_dir, "server")
client_dir = os.path.join(base_dir, "client")
server_config_path = os.path.join(server_dir, "server_config.json")
client_config_path = os.path.join(client_dir, "client_config.json")


def update_file(path, pattern, replacement):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        print(f"Updated: {path}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    else:
        print(f"No changes needed in: {path}")


with open(version_info_file, "r", encoding="utf-8") as f:
    version = json.load(f)["version"]

update_file(
    readme_md_path,
    r"Version: \d+\.\d+\.\d+",
    f"Version: {version}"
)
update_file(
    server_config_path,
    r'"version":\s*"\d+\.\d+\.\d+"',
    f'"version": "{version}"'
)
update_file(
    client_config_path,
    r'"version":\s*"\d+\.\d+\.\d+"',
    f'"version": "{version}"'
)

print("Version update completed.")
