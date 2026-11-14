import sys
import json
sys.path.insert(0, "apps/api")
from app.main import app

routes = []
for route in app.routes:
    methods = sorted(list(getattr(route, "methods", [])))
    path = getattr(route, "path", None)
    name = getattr(route, "name", None)
    tags = getattr(route, "tags", [])
    routes.append({
        "path": path,
        "methods": methods,
        "name": name,
        "tags": tags,
    })

routes.sort(key=lambda r: (r["path"] or "", r["methods"]))
print(f"Total Routes Registered: {len(routes)}")
for r in routes:
    methods_str = ",".join(r["methods"]) if r["methods"] else "WS"
    print(f"{methods_str:<10} {r['path']:<55} [{','.join(r['tags'])}]")
