"""
Tests for the ValidationEngine.
No database needed — tests are pure Python.
"""

import pytest

from cad_generator.core.validation_engine import Severity, ValidationEngine


# Default valid parameters for Placa Base
BASE_PARAMS = {
    "largo": 300.0,
    "ancho": 200.0,
    "espesor": 12.0,
    "diametro_perforacion": 18.0,
    "margen_perforacion": 30.0,
    "tiene_ranuras": False,
    "ancho_ranura": 12.0,
    "largo_ranura": 40.0,
}

# Minimal rule set for testing
RULES = [
    {
        "rule_id": "VR-BP-01",
        "expression": "espesor >= 4.0",
        "severity": "error",
        "message": "Espesor m\u00ednimo 4 mm.",
    },
    {
        "rule_id": "VR-BP-02",
        "expression": "max(largo, ancho) / min(largo, ancho) <= 10.0",
        "severity": "warning",
        "message": "Relaci\u00f3n largo/ancho supera 10:1.",
    },
    {
        "rule_id": "VR-BP-04",
        "expression": "margen_perforacion >= diametro_perforacion * 1.5",
        "severity": "error",
        "message": "Margen insuficiente (AISC).",
    },
    {
        "rule_id": "VR-BP-05",
        "expression": "largo >= 2 * margen_perforacion + diametro_perforacion",
        "severity": "error",
        "message": "Largo insuficiente para alojar perforaciones.",
    },
    {
        "rule_id": "VR-BP-07",
        "expression": "not tiene_ranuras or largo_ranura <= largo * 0.6",
        "severity": "warning",
        "message": "Ranura demasiado larga.",
    },
]


class TestValidationEngineValidParameters:

    def test_all_valid_passes(self):
        engine = ValidationEngine()
        result = engine.validate(BASE_PARAMS, RULES)
        assert result.is_valid
        assert result.errors == []
        assert result.warnings == []

    def test_empty_rules_always_passes(self):
        engine = ValidationEngine()
        result = engine.validate(BASE_PARAMS, [])
        assert result.is_valid


class TestValidationEngineErrors:

    def test_thin_plate_fails_vr_bp_01(self):
        params = {**BASE_PARAMS, "espesor": 2.0}
        result = ValidationEngine().validate(params, RULES)
        assert not result.is_valid
        rule_ids = [m.rule_id for m in result.errors]
        assert "VR-BP-01" in rule_ids

    def test_small_margin_fails_vr_bp_04(self):
        # margen=20 < 18*1.5=27 → error
        params = {**BASE_PARAMS, "margen_perforacion": 20.0}
        result = ValidationEngine().validate(params, RULES)
        assert not result.is_valid
        assert any(m.rule_id == "VR-BP-04" for m in result.errors)

    def test_plate_too_short_fails_vr_bp_05(self):
        # largo=60 < 2*30+18=78 → error
        params = {**BASE_PARAMS, "largo": 60.0}
        result = ValidationEngine().validate(params, RULES)
        assert not result.is_valid
        assert any(m.rule_id == "VR-BP-05" for m in result.errors)


class TestValidationEngineWarnings:

    def test_high_aspect_ratio_gives_warning_not_error(self):
        # ratio = 3000/200 = 15 > 10 → warning only
        params = {**BASE_PARAMS, "largo": 3000.0}
        result = ValidationEngine().validate(params, RULES)
        # Result may still be is_valid=True (no errors)
        warning_ids = [m.rule_id for m in result.warnings]
        assert "VR-BP-02" in warning_ids
        # Should NOT be an error
        error_ids = [m.rule_id for m in result.errors]
        assert "VR-BP-02" not in error_ids

    def test_long_slot_gives_warning(self):
        params = {**BASE_PARAMS, "tiene_ranuras": True, "largo_ranura": 250.0}
        result = ValidationEngine().validate(params, RULES)
        warning_ids = [m.rule_id for m in result.warnings]
        assert "VR-BP-07" in warning_ids


class TestValidationEngineEdgeCases:

    def test_expression_error_becomes_error_message(self):
        bad_rules = [
            {
                "rule_id": "VR-BAD",
                "expression": "undefined_variable > 0",
                "severity": "error",
                "message": "Bad rule.",
            }
        ]
        result = ValidationEngine().validate(BASE_PARAMS, bad_rules)
        assert not result.is_valid
        assert any(m.rule_id == "VR-BAD" for m in result.errors)

    def test_slot_rule_skipped_when_no_slots(self):
        params = {**BASE_PARAMS, "tiene_ranuras": False, "largo_ranura": 999.0}
        result = ValidationEngine().validate(params, RULES)
        # VR-BP-07: not tiene_ranuras or ... → True because tiene_ranuras=False
        warning_ids = [m.rule_id for m in result.warnings]
        assert "VR-BP-07" not in warning_ids
