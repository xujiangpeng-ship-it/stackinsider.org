import os, re
POSTS_DIR = "content/posts"
pattern = re.compile(r'\*{0,2}Related Articles\*{0,2}\s*\n(?:\s*[-*]\s+\[.*?\]\(#.*?\)\s*\n?)+', re.IGNORECASE)
cleaned_count = 0
for root, dirs, files in os.walk(POSTS_DIR):
    for file in files:
        if file.endswith(".md"):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = pattern.sub("", content).rstrip() + "\n"
            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                cleaned_count += 1
print(f"Total cleaned files: {cleaned_count}")
