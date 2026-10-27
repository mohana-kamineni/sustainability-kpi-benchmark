"""
Unit tests for numeric parsing, unit conversion, and normalisation.
"""

import pytest
from src.normalisation import (
    clean_numeric_string,
    parse_target_year,
    normalise_kpi_value,
    compare_kpi_values
)


def test_clean_numeric_string():
    assert clean_numeric_string(78326) == 78326.0
    assert clean_numeric_string("78,326") == 78326.0
    assert clean_numeric_string("78 326") == 78326.0
    assert clean_numeric_string("1,102,607") == 1102607.0
    assert clean_numeric_string("14.9%") == 14.9
    assert clean_numeric_string("14,9") == 14.9  # European decimal
    assert clean_numeric_string("2.3") == 2.3
    assert clean_numeric_string("-") is None
    assert clean_numeric_string("N/A") is None
    assert clean_numeric_string(None) is None


def test_parse_target_year():
    assert parse_target_year(2050) == 2050
    assert parse_target_year("2050") == 2050
    assert parse_target_year("Net-zero by 2050 at the latest") == 2050
    assert parse_target_year("Target 2030") == 2030
    assert parse_target_year("No date specified") is None


def test_normalise_kpi_emissions():
    # Tonnes to tonnes
    v, u = normalise_kpi_value("scope_1_ghg_emissions", 78326, "ton CO2eq")
    assert v == 78326.0
    assert u == "tonnes CO2e"

    # Kilotonnes to tonnes
    v, u = normalise_kpi_value("scope_1_ghg_emissions", 32, "ktCO2e")
    assert v == 32000.0
    assert u == "tonnes CO2e"

    # Thousand tons to tonnes
    v, u = normalise_kpi_value("scope_1_ghg_emissions", "82", "thousand ton CO2eq")
    assert v == 82000.0
    assert u == "tonnes CO2e"


def test_normalise_kpi_energy():
    # MWh unchanged
    v, u = normalise_kpi_value("total_energy_consumption", "1,102,607", "MWh")
    assert v == 1102607.0
    assert u == "MWh"

    # GWh to MWh
    v, u = normalise_kpi_value("total_energy_consumption", 319, "GWh")
    assert v == 319000.0
    assert u == "MWh"


def test_normalise_kpi_renewable_share():
    v, u = normalise_kpi_value("renewable_electricity_share", "14.9", "%")
    assert v == 14.9
    assert u == "%"

    # Decimal fraction 0.149 converted to 14.9%
    v, u = normalise_kpi_value("renewable_electricity_share", 0.149, "")
    assert abs(v - 14.9) < 1e-4


def test_normalise_kpi_sbti():
    # Acceptance test: validated, not validated, not yet validated, committed, verified
    v, u = normalise_kpi_value("sbti_target_status", "validated")
    assert v == "validated" and u == "status"

    v, u = normalise_kpi_value("sbti_target_status", "verified")
    assert v == "validated" and u == "status"

    v, u = normalise_kpi_value("sbti_target_status", "committed")
    assert v == "committed" and u == "status"

    v, u = normalise_kpi_value("sbti_target_status", "not validated")
    assert v == "not_validated" and u == "status"

    v, u = normalise_kpi_value("sbti_target_status", "not yet validated")
    assert v == "not_validated" and u == "status"

    # Target scope distinction: near-term vs long-term net-zero
    v, u = normalise_kpi_value("sbti_target_status", "near-term validated, but long-term net-zero not validated")
    assert v == "near_term_validated" and u == "status"

    v, u = normalise_kpi_value("sbti_target_status", "Targets approved and validated by SBTi")
    assert v == "validated"
    assert u == "status"

    v, u = normalise_kpi_value("sbti_target_status", "Committed to setting targets")
    assert v == "committed"


def test_compare_kpi_values():
    # Within 2% tolerance
    assert compare_kpi_values(78326.0, 78326.0, "scope_1_ghg_emissions", rel_tol=0.02)
    assert compare_kpi_values(78000.0, 78326.0, "scope_1_ghg_emissions", rel_tol=0.02)
    assert not compare_kpi_values(70000.0, 78326.0, "scope_1_ghg_emissions", rel_tol=0.02)

    # SBTi status matching and negation safety
    assert compare_kpi_values("validated", "validated", "sbti_target_status")
    assert compare_kpi_values("SBTi approved", "validated", "sbti_target_status")
    assert compare_kpi_values("verified", "validated", "sbti_target_status")
    assert not compare_kpi_values("not validated", "validated", "sbti_target_status")
    assert not compare_kpi_values("not yet validated", "validated", "sbti_target_status")
    assert not compare_kpi_values("unvalidated", "validated", "sbti_target_status")

    # Target year
    assert compare_kpi_values(2050, 2050, "net_zero_target_year")
    assert not compare_kpi_values(2045, 2050, "net_zero_target_year")

    # None handling
    assert compare_kpi_values(None, None, "scope_1_ghg_emissions")
    assert not compare_kpi_values(100, None, "scope_1_ghg_emissions")
