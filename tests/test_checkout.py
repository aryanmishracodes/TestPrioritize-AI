"""
tests/test_checkout.py
Unit tests for checkout operations in src/checkout.py.
"""

import pytest
from src.checkout import (
    FREE_SHIPPING_THRESHOLD,
    apply_discount,
    qualifies_for_free_shipping,
)


# ============================================================================
# apply_discount Tests
# ============================================================================


def test_apply_discount_standard_percentage():
    """Applying a typical 10% discount to $100.00 should yield $90.00."""
    assert apply_discount(100.0, 10.0) == 90.0


def test_apply_discount_fractional_result_rounds_correctly():
    """Discounts resulting in fractional cents should round to 2 decimal places."""
    # 49.99 * 0.15 = 7.4985 discount -> 49.99 - 7.4985 = 42.4915 -> 42.49
    assert apply_discount(49.99, 15.0) == 42.49


def test_apply_discount_zero_percent():
    """A 0% discount must return the exact original total without reduction."""
    assert apply_discount(75.50, 0.0) == 75.50


def test_apply_discount_one_hundred_percent():
    """A 100% discount should reduce any order total to 0.0."""
    assert apply_discount(129.99, 100.0) == 0.0


def test_apply_discount_zero_total():
    """Applying a discount to a 0.0 total should return 0.0."""
    assert apply_discount(0.0, 20.0) == 0.0


def test_apply_discount_negative_percentage_raises_value_error():
    """Negative discount percentages must be rejected."""
    with pytest.raises(ValueError, match="between 0 and 100"):
        apply_discount(100.0, -5.0)


def test_apply_discount_exceeding_hundred_percent_raises_value_error():
    """Discounts exceeding 100% must be rejected."""
    with pytest.raises(ValueError, match="between 0 and 100"):
        apply_discount(100.0, 105.0)


def test_apply_discount_negative_total_raises_value_error():
    """Negative totals must be rejected."""
    with pytest.raises(ValueError, match="cannot be negative"):
        apply_discount(-50.0, 10.0)


def test_apply_discount_non_numeric_total_raises_type_error():
    """Non-numeric total must raise TypeError."""
    with pytest.raises(TypeError, match="must be a number"):
        apply_discount("100", 10.0)  # type: ignore


def test_apply_discount_non_numeric_percent_raises_type_error():
    """Non-numeric discount percent must raise TypeError."""
    with pytest.raises(TypeError, match="must be a number"):
        apply_discount(100.0, "ten_percent")  # type: ignore


def test_apply_discount_boolean_input_raises_type_error():
    """Booleans must not be accepted as numbers."""
    with pytest.raises(TypeError, match="must be a number"):
        apply_discount(True, 10.0)  # type: ignore


# ============================================================================
# qualifies_for_free_shipping Tests
# ============================================================================


def test_qualifies_for_free_shipping_strictly_above_threshold():
    """Orders greater than $50.00 qualify for free shipping."""
    assert qualifies_for_free_shipping(75.00) is True


def test_qualifies_for_free_shipping_exactly_at_threshold():
    """Orders matching the threshold ($50.00) qualify for free shipping."""
    assert qualifies_for_free_shipping(FREE_SHIPPING_THRESHOLD) is True


def test_qualifies_for_free_shipping_one_cent_below_threshold():
    """Orders just below $50.00 ($49.99) do not qualify for free shipping."""
    assert qualifies_for_free_shipping(49.99) is False


def test_qualifies_for_free_shipping_zero_total():
    """A zero total does not qualify for free shipping."""
    assert qualifies_for_free_shipping(0.0) is False


def test_qualifies_for_free_shipping_negative_total_raises_value_error():
    """Negative totals must be rejected with ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        qualifies_for_free_shipping(-10.0)


