import json

with open("openapi_dump.json", "r", encoding="utf-8-sig") as f:
    data = json.load(f)

paths = data.get("paths", {})
print(f"Total OpenAPI Paths: {len(paths)}")

operations = []
by_tag = {}

for path, methods in paths.items():
    for method, op in methods.items():
        if method.lower() not in ("get", "post", "put", "patch", "delete"):
            continue
        tags = op.get("tags", ["Uncategorized"])
        tag = tags[0] if tags else "Uncategorized"
        by_tag.setdefault(tag, []).append((method.upper(), path, op.get("summary", "")))
        operations.append((method.upper(), path, tag, op.get("security", [])))

print(f"Total API Operations: {len(operations)}")
print("\n--- Operations by Domain Tag ---")
for tag, ops in sorted(by_tag.items()):
    print(f"\n[{tag}] ({len(ops)} endpoints):")
    for m, p, s in ops:
        print(f"  {m:<7} {p}")
