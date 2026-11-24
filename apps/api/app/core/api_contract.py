"""
The API contract: a committed OpenAPI snapshot, and a check that changes to it don't break
apps already in people's hands.

    python -m app.core.api_contract export          # rewrite the snapshot from the code
    python -m app.core.api_contract check           # fail if the snapshot is out of date
    python -m app.core.api_contract compat OLD.json # fail on breaking changes since OLD

The snapshot (`packages/contracts/openapi/v1.json`) is what the Android and iOS apps generate
their API clients from. CI runs `check`, and `compat` against the previous commit's snapshot.

What counts as breaking, for an app built against the old contract:
  * an operation removed, or its success status changed;
  * a new required parameter or request field, a request body that became required, a
    request field or parameter that accepts fewer types, enum values or a shorter length;
  * a response field removed, no longer always present, or of a different type (including
    newly nullable), and new enum values in a response (strict decoders reject them).
Adding operations, optional request fields and response fields is not breaking.

A breaking change can still be intended (nothing released depends on it yet, or the minimum
app version was raised first). List each reported line in
`packages/contracts/openapi/accepted-breaking-changes.txt` in the same commit, with a note.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT = REPO_ROOT / "packages" / "contracts" / "openapi" / "v1.json"
ACCEPTED = REPO_ROOT / "packages" / "contracts" / "openapi" / "accepted-breaking-changes.txt"

METHODS = ("get", "put", "post", "delete", "patch")
MAX_DEPTH = 12

Spec = Dict[str, Any]
Schema = Dict[str, Any]


def current_spec() -> Spec:
    from app.main import app

    app.openapi_schema = None
    return app.openapi()


def dumps(spec: Spec) -> str:
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------- schema helpers

def _resolve(spec: Spec, schema: Optional[Schema]) -> Schema:
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema and seen < MAX_DEPTH:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec.get("components", {}).get("schemas", {}).get(name, {})
        seen += 1
    return schema or {}


def _members(spec: Spec, schema: Schema) -> List[Schema]:
    """The alternatives of a union (anyOf/oneOf), or the schema itself."""
    schema = _resolve(spec, schema)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            out: List[Schema] = []
            for member in schema[key]:
                out.extend(_members(spec, member))
            return out
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _members(spec, schema["allOf"][0])
    return [schema]


def _types(spec: Spec, schema: Schema) -> Set[str]:
    types: Set[str] = set()
    for member in _members(spec, schema):
        t = member.get("type")
        if t is None:
            types.add("object" if "properties" in member else "any")
        elif isinstance(t, list):
            types.update(t)
        else:
            types.add(t)
    return types


def _main(spec: Spec, schema: Schema) -> Optional[Schema]:
    """The single non-null alternative of a union (Optional[X] -> X), if there is one."""
    real = [m for m in _members(spec, schema) if m.get("type") != "null"]
    return real[0] if len(real) == 1 else None


def _enum(spec: Spec, schema: Schema) -> Optional[Set[Any]]:
    values: Set[Any] = set()
    for member in _members(spec, schema):
        if member.get("type") == "null":
            continue
        if "enum" in member:
            values.update(json.dumps(v) for v in member["enum"])
        elif "const" in member:
            values.add(json.dumps(member["const"]))
        else:
            return None  # an open alternative: not an enum
    return values or None


def _widen(types: Set[str]) -> Set[str]:
    # An integer is also a number.
    return types | ({"number"} if "integer" in types else set())


def _compare(spec_old: Spec, spec_new: Spec, old: Schema, new: Schema, direction: str,
             where: str, problems: List[str], depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        return
    t_old, t_new = _types(spec_old, old), _types(spec_new, new)
    if "any" not in t_old and "any" not in t_new:
        if direction == "out" and not t_new <= _widen(t_old):
            problems.append(f"{where}: response type changed from {sorted(t_old)} to {sorted(t_new)}")
            return
        if direction == "in" and not t_old <= _widen(t_new):
            problems.append(f"{where}: no longer accepts {sorted(t_old - _widen(t_new))}")
            return
    e_old, e_new = _enum(spec_old, old), _enum(spec_new, new)
    if direction == "out" and e_old is not None and e_new is not None and e_new - e_old:
        problems.append(f"{where}: new response values {sorted(e_new - e_old)}")
    if direction == "in" and e_old is not None and e_new is not None and e_old - e_new:
        problems.append(f"{where}: no longer accepts values {sorted(e_old - e_new)}")

    m_old, m_new = _main(spec_old, old), _main(spec_new, new)
    if m_old is None or m_new is None:
        return
    if direction == "in":
        for key, tighter in (("maxLength", lambda o, n: n < o), ("maxItems", lambda o, n: n < o),
                             ("maximum", lambda o, n: n < o), ("minLength", lambda o, n: n > o),
                             ("minimum", lambda o, n: n > o)):
            o, n = m_old.get(key), m_new.get(key)
            if n is not None and (o is None or tighter(o, n)):
                problems.append(f"{where}: {key} tightened from {o} to {n}")

    p_old, p_new = m_old.get("properties"), m_new.get("properties")
    if isinstance(p_old, dict) and isinstance(p_new, dict):
        r_old, r_new = set(m_old.get("required", [])), set(m_new.get("required", []))
        if direction == "out":
            for name, sub in p_old.items():
                if name not in p_new:
                    problems.append(f"{where}.{name}: response field removed")
                    continue
                if name in r_old and name not in r_new:
                    problems.append(f"{where}.{name}: response field no longer always present")
                _compare(spec_old, spec_new, sub, p_new[name], direction, f"{where}.{name}", problems, depth + 1)
        else:
            for name in sorted(r_new - r_old):
                problems.append(f"{where}.{name}: new required request field")
            for name, sub in p_old.items():
                if name in p_new:
                    _compare(spec_old, spec_new, sub, p_new[name], direction, f"{where}.{name}", problems, depth + 1)
    if "items" in m_old and "items" in m_new:
        _compare(spec_old, spec_new, m_old["items"], m_new["items"], direction, f"{where}[]", problems, depth + 1)


# ---------------------------------------------------------------------------- operations

def _operations(spec: Spec) -> Dict[Tuple[str, str], Schema]:
    return {
        (method.upper(), path): op
        for path, item in spec.get("paths", {}).items()
        for method, op in item.items() if method in METHODS
    }


def _json_schema(content: Optional[Dict[str, Any]]) -> Optional[Schema]:
    if not content:
        return None
    for media in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
        if media in content:
            return content[media].get("schema")
    return None


def _success(op: Schema) -> Dict[str, Schema]:
    return {code: resp for code, resp in op.get("responses", {}).items() if str(code).startswith("2")}


def _params(op: Schema) -> Dict[Tuple[str, str], Schema]:
    return {(p.get("in", ""), p.get("name", "")): p for p in op.get("parameters", [])}


def breaking_changes(old: Spec, new: Spec) -> List[str]:
    problems: List[str] = []
    ops_new = _operations(new)
    for key, op_old in sorted(_operations(old).items()):
        label = f"{key[0]} {key[1]}"
        op_new = ops_new.get(key)
        if op_new is None:
            problems.append(f"{label}: operation removed")
            continue
        # Parameters.
        p_old, p_new = _params(op_old), _params(op_new)
        for pkey, param in sorted(p_new.items()):
            if param.get("required") and not p_old.get(pkey, {}).get("required"):
                problems.append(f"{label}: new required {pkey[0]} parameter '{pkey[1]}'")
        for pkey, param in sorted(p_old.items()):
            if pkey in p_new:
                _compare(old, new, param.get("schema", {}), p_new[pkey].get("schema", {}), "in",
                         f"{label} {pkey[0]} parameter '{pkey[1]}'", problems)
        # Request body.
        b_old, b_new = op_old.get("requestBody"), op_new.get("requestBody")
        if b_new and b_new.get("required") and not (b_old and b_old.get("required")):
            problems.append(f"{label}: request body is now required")
        s_old, s_new = _json_schema((b_old or {}).get("content")), _json_schema((b_new or {}).get("content"))
        if s_old is not None and s_new is not None:
            _compare(old, new, s_old, s_new, "in", f"{label} request", problems)
        # Success responses.
        r_old, r_new = _success(op_old), _success(op_new)
        if r_old and r_new and not set(r_old) & set(r_new):
            problems.append(f"{label}: success status changed from {sorted(r_old)} to {sorted(r_new)}")
        for code in sorted(set(r_old) & set(r_new)):
            s_old = _json_schema(r_old[code].get("content"))
            s_new = _json_schema(r_new[code].get("content"))
            if s_old is not None and s_new is not None:
                _compare(old, new, s_old, s_new, "out", f"{label} {code} response", problems)
    return problems


def accepted_changes(path: Path = ACCEPTED) -> Set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")}


def unaccepted(problems: Iterable[str], accepted: Set[str]) -> List[str]:
    return [p for p in problems if p not in accepted]


# ---------------------------------------------------------------------------- command line

def main(argv: List[str]) -> int:
    command = argv[0] if argv else "check"
    if command == "export":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(dumps(current_spec()), encoding="utf-8")
        print(f"Wrote {SNAPSHOT.relative_to(REPO_ROOT)}")
        return 0
    if command == "check":
        if not SNAPSHOT.exists() or json.loads(SNAPSHOT.read_text(encoding="utf-8")) != json.loads(dumps(current_spec())):
            print("The API changed but packages/contracts/openapi/v1.json didn't. "
                  "Run `python -m app.core.api_contract export` in apps/api and commit the result.")
            return 1
        print("API contract snapshot is up to date.")
        return 0
    if command == "compat" and len(argv) == 2:
        old = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        new = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        problems = unaccepted(breaking_changes(old, new), accepted_changes())
        for line in problems:
            print(line)
        if problems:
            print(f"\n{len(problems)} breaking API change(s). Keep the old behaviour, add a new field or "
                  f"endpoint instead, or (if intended) list the lines above in "
                  f"{ACCEPTED.relative_to(REPO_ROOT)}.")
            return 1
        print("No breaking API changes.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
