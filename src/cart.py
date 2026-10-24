"""
src/cart.py
Cart management and total calculation logic.
"""

from typing import Any, Dict, List, Union


def calculate_cart_total(items: List[Dict[str, Any]]) -> float:
    """
    Calculate the total cost of all items in a shopping cart.

    Rules & Edge Cases:
    - items must be a list of dictionaries.
    - Each item dictionary must contain a numeric 'price' (>= 0).
    - An optional 'quantity' field can be provided (default is 1, must be >= 0).
    - Empty cart returns 0.0.
    - Negative prices or negative quantities raise ValueError.
    - Non-list input raises TypeError.

    Args:
        items: List of dictionaries representing items in the cart.
               Example: [{"name": "Book", "price": 12.50, "quantity": 2}]

    Returns:
        float: Total rounded to 2 decimal places.

    Raises:
        TypeError: If items is not a list.
        ValueError: If price or quantity is invalid or negative.
    """
    if not isinstance(items, list):
        raise TypeError("Cart items must be provided as a list.")

    if not items:
        return 0.0

    total = 0.0

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise TypeError(f"Cart item at index {idx} must be a dictionary.")

        if "price" not in item:
            raise ValueError(f"Cart item at index {idx} is missing required 'price' key.")

        price = item["price"]
        if not isinstance(price, (int, float)):
            raise TypeError(f"Item price at index {idx} must be a number, got {type(price).__name__}.")

        if price < 0:
            raise ValueError(f"Item price at index {idx} cannot be negative: {price}.")

        quantity = item.get("quantity", 1)
        if not isinstance(quantity, (int, float)):
            raise TypeError(f"Item quantity at index {idx} must be a number, got {type(quantity).__name__}.")

        if quantity < 0:
            raise ValueError(f"Item quantity at index {idx} cannot be negative: {quantity}.")

        total += price * quantity

    return round(total, 2)
