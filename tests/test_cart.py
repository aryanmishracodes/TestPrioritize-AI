"""
tests/test_cart.py
Unit tests for cart operations in src/cart.py.
"""

import pytest
from src.cart import calculate_cart_total


def test_calculate_cart_total_empty_cart():
    """An empty cart list should evaluate to a total of 0.0."""
    assert calculate_cart_total([]) == 0.0


def test_calculate_cart_total_single_item_default_quantity():
    """A single item without quantity specified should default to quantity 1."""
    items = [{"name": "Mechanical Pencil", "price": 4.99}]
    assert calculate_cart_total(items) == 4.99


def test_calculate_cart_total_single_item_with_quantity():
    """A single item with multiple units should multiply price by quantity."""
    items = [{"name": "Notebook", "price": 3.50, "quantity": 4}]
    assert calculate_cart_total(items) == 14.00


def test_calculate_cart_total_multiple_distinct_items():
    """Multiple items should be summed accurately."""
    items = [
        {"name": "Keyboard", "price": 45.00, "quantity": 1},
        {"name": "Mouse", "price": 25.50, "quantity": 2},
        {"name": "Stickers", "price": 1.25, "quantity": 4},
    ]
    # 45.00 + (25.50 * 2 = 51.00) + (1.25 * 4 = 5.00) = 101.00
    assert calculate_cart_total(items) == 101.00


def test_calculate_cart_total_floating_point_rounding():
    """Monetary totals should round to 2 decimal places to avoid float artifacts."""
    items = [
        {"name": "Widget A", "price": 19.99, "quantity": 3},  # 59.97
        {"name": "Widget B", "price": 0.01, "quantity": 1},   # 0.01
    ]
    assert calculate_cart_total(items) == 59.98


def test_calculate_cart_total_zero_price_item():
    """Items with zero price (promotional/free items) are valid and contribute 0.0."""
    items = [{"name": "Free Sample", "price": 0.0, "quantity": 1}]
    assert calculate_cart_total(items) == 0.0


def test_calculate_cart_total_zero_quantity_item():
    """Items with zero quantity are valid and contribute 0.0 to the total."""
    items = [{"name": "Unselected Item", "price": 20.00, "quantity": 0}]
    assert calculate_cart_total(items) == 0.0


def test_calculate_cart_total_negative_price_raises_value_error():
    """Negative prices must be rejected with ValueError."""
    items = [{"name": "Corrupted Item", "price": -5.00, "quantity": 1}]
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_cart_total(items)


def test_calculate_cart_total_negative_quantity_raises_value_error():
    """Negative quantities must be rejected with ValueError."""
    items = [{"name": "Invalid Quantity Item", "price": 10.00, "quantity": -2}]
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_cart_total(items)


def test_calculate_cart_total_missing_price_raises_value_error():
    """Cart items missing the required 'price' key must raise ValueError."""
    items = [{"name": "No Price Item", "quantity": 1}]
    with pytest.raises(ValueError, match="missing required 'price' key"):
        calculate_cart_total(items)


def test_calculate_cart_total_non_list_input_raises_type_error():
    """Passing a non-list as items input must raise TypeError."""
    with pytest.raises(TypeError, match="must be provided as a list"):
        calculate_cart_total("invalid_cart_string")  # type: ignore



