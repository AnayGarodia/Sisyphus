import os
import re

#  Change this to your folder path
folder = "/Users/aakritigarodia/Documents/Coding/Sisyphus"

#  File types to clean
valid_extensions = {".py", ".html", ".css", ".js", ".txt", ".md", ".json", ".yml"}

#  Emoji pattern
emoji_pattern = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # miscellaneous symbols
    "]+",
    flags=re.UNICODE
)

#  Walk through the folder
for root, _, files in os.walk(folder):
    for filename in files:
        _, ext = os.path.splitext(filename)
        if ext.lower() not in valid_extensions:
            continue  # skip files like .pyc, .png, etc.

        filepath = os.path.join(root, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            print(f"️ Skipping non-UTF8 file: {filepath}")
            continue

        new_content = emoji_pattern.sub("", content)
        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f" Removed emojis from {filepath}")

print(" Done! All emojis removed from .py, .html, .css, etc.")
