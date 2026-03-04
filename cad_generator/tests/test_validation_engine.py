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


# ---------------------------------------------------------------------------
# Semana 9 — new rules: VR-BP-09, VR-BP-10, VR-BP-11
# ---------------------------------------------------------------------------

# Extended base params (includes patron_perforaciones for spacing rules)
_BASE_EXT = {
    **BASE_PARAMS,
    "patron_perforaciones": "rectangular_4",
}

_NEW_RULES = [
    {
        "rule_id": "VR-BP-09",
        "expression": (
            'patron_perforaciones == "none" or '
            "(largo - 2 * margen_perforacion) >= 3 * diametro_perforacion"
        ),
        "severity": "error",
        "message": "Separación longitudinal insuficiente (AISC J3.3).",
    },
    {
        "rule_id": "VR-BP-10",
        "expression": "not tiene_ranuras or largo_ranura <= 8 * ancho_ranura",
        "severity": "warning",
        "message": "Relación largo/ancho de ranura supera 8:1.",
    },
    {
        "rule_id": "VR-BP-11",
        "expression": (
            'patron_perforaciones in ("none", "lineal_2", "personalizado") or '
            "(ancho - 2 * margen_perforacion) >= 3 * diametro_perforacion"
        ),
        "severity": "error",
        "message": "Separación transversal insuficiente para patrón rectangular (AISC J3.3).",
    },
]


class TestVRBP09LongitudinalSpacing:
    """VR-BP-09: (largo - 2×margen) ≥ 3×d  (skipped when patron == 'none')."""

    def test_no_holes_always_passes(self):
        params = {**_BASE_EXT, "patron_perforaciones": "none"}
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-09" not in [m.rule_id for m in result.errors]

    def test_sufficient_spacing_passes(self):
        # (300 - 2×30) = 240  ≥  3×18 = 54  → pass
        result = ValidationEngine().validate(_BASE_EXT, _NEW_RULES)
        assert "VR-BP-09" not in [m.rule_id for m in result.errors]

    def test_insufficient_longitudinal_spacing_fails(self):
        # (100 - 2×25) = 50  <  3×18 = 54  → error
        params = {
            **_BASE_EXT,
            "largo": 100.0,
            "margen_perforacion": 25.0,
            "diametro_perforacion": 18.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-09" in [m.rule_id for m in result.errors]

    def test_lineal_pattern_also_checked(self):
        # lineal_2 is NOT "none", so the spacing is still validated
        # (100 - 2×25) = 50 < 54 → error
        params = {
            **_BASE_EXT,
            "patron_perforaciones": "lineal_2",
            "largo": 100.0,
            "margen_perforacion": 25.0,
            "diametro_perforacion": 18.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-09" in [m.rule_id for m in result.errors]


class TestVRBP10SlotAspectRatio:
    """VR-BP-10: largo_ranura ≤ 8 × ancho_ranura  (warning, skipped when no slots)."""

    def test_no_slots_always_passes(self):
        params = {**_BASE_EXT, "tiene_ranuras": False}
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-10" not in [m.rule_id for m in result.warnings]

    def test_acceptable_ratio_passes(self):
        # 40 / 12 ≈ 3.3  ≤  8  → pass
        params = {
            **_BASE_EXT,
            "tiene_ranuras": True,
            "largo_ranura": 40.0,
            "ancho_ranura": 12.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-10" not in [m.rule_id for m in result.warnings]

    def test_excessive_ratio_gives_warning(self):
        # 100 / 10 = 10  >  8  → warning
        params = {
            **_BASE_EXT,
            "tiene_ranuras": True,
            "largo_ranura": 100.0,
            "ancho_ranura": 10.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-10" in [m.rule_id for m in result.warnings]

    def test_vr_bp_10_is_warning_not_error(self):
        # Even when triggered, must be a warning, never an error
        params = {
            **_BASE_EXT,
            "tiene_ranuras": True,
            "largo_ranura": 100.0,
            "ancho_ranura": 10.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-10" not in [m.rule_id for m in result.errors]


class TestVRBP11TransversalSpacing:
    """VR-BP-11: (ancho - 2×margen) ≥ 3×d  for rectangular patterns only."""

    def test_no_holes_skips_rule(self):
        params = {**_BASE_EXT, "patron_perforaciones": "none"}
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-11" not in [m.rule_id for m in result.errors]

    def test_lineal_pattern_skips_rule(self):
        params = {**_BASE_EXT, "patron_perforaciones": "lineal_2"}
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-11" not in [m.rule_id for m in result.errors]

    def test_personalizado_pattern_skips_rule(self):
        params = {**_BASE_EXT, "patron_perforaciones": "personalizado"}
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-11" not in [m.rule_id for m in result.errors]

    def test_rectangular_sufficient_transversal_passes(self):
        # (200 - 2×30) = 140  ≥  3×18 = 54  → pass
        params = {
            **_BASE_EXT,
            "patron_perforaciones": "rectangular_4",
            "ancho": 200.0,
            "margen_perforacion": 30.0,
            "diametro_perforacion": 18.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-11" not in [m.rule_id for m in result.errors]

    def test_rectangular_insufficient_transversal_fails(self):
        # (100 - 2×25) = 50  <  3×18 = 54  → error
        params = {
            **_BASE_EXT,
            "patron_perforaciones": "rectangular_4",
            "ancho": 100.0,
            "margen_perforacion": 25.0,
            "diametro_perforacion": 18.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-11" in [m.rule_id for m in result.errors]

    def test_rectangular_6_also_checked(self):
        # rectangular_6 is also a rectangular pattern — must be validated
        # (100 - 2×25) = 50 < 54 → error
        params = {
            **_BASE_EXT,
            "patron_perforaciones": "rectangular_6",
            "ancho": 100.0,
            "margen_perforacion": 25.0,
            "diametro_perforacion": 18.0,
        }
        result = ValidationEngine().validate(params, _NEW_RULES)
        assert "VR-BP-11" in [m.rule_id for m in result.errors]
