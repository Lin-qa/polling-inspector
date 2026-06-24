from __future__ import annotations

import re


def apply_variables(text: str, variables: dict[str, str]) -> str:
    result = text or ""
    for key, value in variables.items():
        result = result.replace(f"${{{key}}}", str(value))
    return result


def unresolved_variables(*values: object) -> list[str]:
    unresolved: list[str] = []
    for value in values:
        unresolved.extend(re.findall(r"\$\{[^}]+}", str(value or "")))
    return sorted(set(unresolved))

