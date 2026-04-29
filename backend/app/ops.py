from __future__ import annotations

from app.schema import FieldDef


class OpError(ValueError):
    pass


def _field(state: dict, name: str) -> FieldDef:
    for f in state["schema"]:
        if f.name == name:
            return f
    raise OpError(f"unknown field '{name}'")


def apply_op(state: dict, op: dict) -> None:
    """Mutate state['values'] according to op. state has keys: schema, values, original_extracted."""
    kind = op.get("op")
    name = op.get("field")
    if not isinstance(name, str):
        raise OpError("op.field is required")
    f = _field(state, name)

    if kind == "set":
        if f.type != "string":
            raise OpError(f"'set' only valid for scalar fields; '{name}' is {f.type}")
        value = op.get("value")
        if not isinstance(value, str):
            raise OpError("op.value must be a string")
        state["values"][name] = value
        return

    if kind == "append":
        if f.type != "list[string]":
            raise OpError(f"'append' only valid for list fields; '{name}' is {f.type}")
        value = op.get("value")
        if not isinstance(value, str):
            raise OpError("op.value must be a string")
        current = state["values"].setdefault(name, [])
        if value not in current:
            current.append(value)
        return

    if kind == "remove":
        if f.type != "list[string]":
            raise OpError(f"'remove' only valid for list fields; '{name}' is {f.type}")
        idx = op.get("index")
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise OpError("op.index must be an int")
        current = state["values"].get(name, [])
        if idx < 0 or idx >= len(current):
            raise OpError(f"index {idx} out of range")
        current.pop(idx)
        return

    if kind == "revert":
        original = state["original_extracted"].get(name)
        if original is not None:
            if f.type == "string" and not isinstance(original, str):
                raise OpError(f"original for '{name}' is not a string")
            if f.type == "list[string]" and not isinstance(original, list):
                raise OpError(f"original for '{name}' is not a list")
        if original is None:
            state["values"][name] = "" if f.type == "string" else []
        else:
            # Copy to avoid sharing the list
            state["values"][name] = list(original) if isinstance(original, list) else original
        return

    raise OpError(f"unknown op '{kind}'")
