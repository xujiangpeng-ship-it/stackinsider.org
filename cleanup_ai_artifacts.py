import os, re
POSTS_DIR = "content/posts"
pattern_codeblock = re.compile(r'^```.*?```', re.DOTALL)
pattern_citation = re.compile(r'^CITATION FORMAT.*?(\n\n|$)', re.IGNORECASE | re.DOTALL)
pattern_tools = re.compile(r'^TOOLS[\s\S]*?(\n\n|$)', re.IGNORECASE)
pattern_xml = re.compile(r'^<[^>]+>.*?(\n\n|$)', re.IGNORECASE)
cleaned_count = 0
for root, dirs, files in os.walk(POSTS_DIR):
    for file in files:
        if file.endswith(".md"):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            parts = content.split("---", 2)
            if len(parts) < 3: continue
            front_matter, body = parts[1], parts[2].lstrip()
            original_body = body
            body = pattern_codeblock.sub("", body)
            body = pattern_citation.sub("", body)
            body = pattern_tools.sub("", body)
            body = pattern_xml.sub("", body)
            body = re.sub(r'^# .+\n\n?', '', body)
            body = body.lstrip()
            if body != original_body:
                new_content = f"---{front_matter}---\n{body}"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                cleaned_count += 1
print(f"Total cleaned files: {cleaned_count}")
