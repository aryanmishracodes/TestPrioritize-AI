"""
src/checkout.py
Checkout operations including discounts and shipping qualification.
"""

from typing import Union

# Minimum order total required to qualify for complimentary free shipping
FREE_SHIPPING_THRESHOLD: float = 50.0


def apply_discount(
    total: Union[int, float],
    discount_percent: Union[int, float]
) -> float:
    """
    Apply a percentage discount to an order total.

    Rules & Edge Cases:
    - total must be a non-negative number (>= 0).
    - discount_percent must be between 0.0 and 100.0 (inclusive).
    - discount_percent of 0 returns the original total.
    - discount_percent of 100 returns 0.0.
    - Negative total raises ValueError.
    - Discount outside [0, 100] raises ValueError.
    - Non-numeric inputs raise TypeError.

    Args:
        total: Original order total amount.
        discount_percent: Percentage discount to apply (0 to 100).

    Returns:
        float: Discounted total rounded to 2 decimal places.

    Raises:
        TypeError: If total or discount_percent is not numeric.
        ValueError: If total is negative or discount_percent is out of range.
    """
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        raise TypeError(f"Total must be a number, got {type(total).__name__}.")

    if not isinstance(discount_percent, (int, float)) or isinstance(discount_percent, bool):
        raise TypeError(
            f"Discount percent must be a number, got {type(discount_percent).__name__}."
        )

    if total < 0:
        raise ValueError(f"Order total cannot be negative: {total}.")

    if discount_percent < 0 or discount_percent > 100:
        raise ValueError(
            f"Discount percent must be between 0 and 100, got: {discount_percent}."
        )

    discount_amount = total * (discount_percent / 100.0)
    discounted_total = total - discount_amount

    return round(discounted_total, 2)


def qualifies_for_free_shipping(total: Union[int, float]) -> bool:
    """
    Determine whether an order qualifies for free shipping.

    Rules & Edge Cases:
    - Orders with total >= FREE_SHIPPING_THRESHOLD ($50.00) qualify for free shipping.
    - Orders below $50.00 do not qualify.
    - Total must be a non-negative number.
    - Negative total raises ValueError.
    - Non-numeric inputs raise TypeError.

    Args:
        total: Final order total amount.

    Returns:
        bool: True if eligible for free shipping, False otherwise.

    Raises:
        TypeError: If total is not numeric.
        ValueError: If total is negative.
    """
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        raise TypeError(f"Total must be a number, got {type(total).__name__}.")

    if total < 0:
        raise ValueError(f"Order total cannot be negative: {total}.")

    return total >= FREE_SHIPPING_THRESHOLD
