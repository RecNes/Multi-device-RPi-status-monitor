"""Script to update version numbers in multiple files based on version.json."""
import json
import re
import os


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
version_info_file = os.path.join(base_dir, "version.json")
readme_md_path = os.path.join(base_dir, "README.md")
server_config_path = os.path.join(base_dir, "server", "server_config.json")
client_config_path = os.path.join(base_dir, "client", "client_config.json")


def update_file(path, pattern, replacement):
    """Update the version in a file based on a regex pattern."""
    with open(path, "r", encoding="utf-8") as f2:
        content = f2.read()
    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        print(f"Updated: {path}")
        with open(path, "w", encoding="utf-8") as f3:
            f3.write(new_content)
    else:
        print(f"No changes needed in: {path}")


with open(version_info_file, "r", encoding="utf-8") as f1:
    version = json.load(f1)["version"]

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
