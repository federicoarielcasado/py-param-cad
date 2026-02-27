"""
ValidationEngine — parameter validation against rules defined in piece_catalog.json.

Each rule has:
  - rule_id: string identifier (e.g., "VR-BP-01")
  - expression: Python expression string evaluated against parameter namespace
  - severity: "error" | "warning"
  - message: human-readable description shown to the user

Rules are evaluated via a restricted eval() with only the parameter dict
and safe math functions as the namespace. The catalog JSON is a trusted
local file, so this is acceptable for a single-user desktop application.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationMessage:
    rule_id: str
    severity: Severity
    message: str


@dataclass
class ValidationResult:
    is_valid: bool              # True only if there are no errors (warnings are allowed)
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.WARNING]


class ValidationEngine:
    """
    Evaluates validation rules for a given parameter set.
    Rules are loaded from the piece_catalog.json validation_rules array.
    """

    # Safe globals available inside rule expressions
    _SAFE_GLOBALS: dict = {
        "__builtins__": {},
        "max": max,
        "min": min,
        "abs": abs,
        "round": round,
        "sqrt": math.sqrt,
        "pi": math.pi,
    }

    def validate(self, parameters: dict, rules: list[dict]) -> ValidationResult:
        """
        Evaluate all rules against parameters.

        Args:
            parameters: Dict of param name -> value (already type-coerced).
            rules: List of rule dicts from piece_catalog.json.

        Returns:
            ValidationResult with all collected messages.
        """
        messages: list[ValidationMessage] = []

        for rule in rules:
            rule_id = rule.get("rule_id", "UNKNOWN")
            expression = rule.get("expression", "True")
            severity = Severity(rule.get("severity", "error"))
            message = rule.get("message", "Validation failed.")

            try:
                passed = bool(eval(expression, self._SAFE_GLOBALS, parameters))  # noqa: S307
            except Exception as exc:
                messages.append(ValidationMessage(
                    rule_id=rule_id,
                    severity=Severity.ERROR,
                    message=f"[Error evaluando regla: {exc}] {message}",
                ))
                continue

            if not passed:
                messages.append(ValidationMessage(
                    rule_id=rule_id,
                    severity=severity,
                    message=message,
                ))

        has_errors = any(m.severity == Severity.ERROR for m in messages)
        return ValidationResult(is_valid=not has_errors, messages=messages)
