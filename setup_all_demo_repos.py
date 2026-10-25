"""
setup_all_demo_repos.py
Part of TestPrioritize AI.

Initializes four complete, independent, reproducible Git demo repositories:
1. ecommerce (E-Commerce Platform): 32 tests (cart, checkout, pricing, inventory)
2. auth_service (Authentication Service): 17 tests (auth, tokens, password hasher, permissions)
3. payment_gateway (Payment Processing Gateway): 17 tests (payment, card validator, invoice, refund)
4. booking_platform (Appointment & Booking Platform): 17 tests (booking, availability, calendar, notifications)

Each repository features:
- Git initialized with baseline commits and tagged scenario branches.
- Meaningful domain logic and genuine pytest unit tests (>= 10 discoverable tests each).
- Clean baseline (all tests pass).
- Deterministic regression scenarios that fail authentically under pytest.
- Realistic AST import relationships for dependency proof demonstrations.
- scenarios.json manifest and README.md documentation.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEMO_REPOS_ROOT = os.path.join(BASE_DIR, "demo_repos")
LEGACY_DEMO_REPO = os.path.join(BASE_DIR, "demo_repo")


def run_git(args: List[str], cwd: str) -> str:
    """Safely runs a Git command in cwd."""
    cmd = ["git"] + args
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def write_file(base_path: str, rel_path: str, content: str) -> None:
    """Safely writes a text file creating parent directories as needed."""
    full_path = os.path.join(base_path, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)


def init_git_repo(target_dir: str) -> None:
    """Initializes Git with standard demo user configuration."""
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    os.makedirs(target_dir, exist_ok=True)

    run_git(["init", "-b", "main"], cwd=target_dir)
    run_git(["config", "user.name", "TestPrioritize Demo Bot"], cwd=target_dir)
    run_git(["config", "user.email", "demo@testprioritize.ai"], cwd=target_dir)
    run_git(["config", "commit.gpgsign", "false"], cwd=target_dir)
    write_file(target_dir, "pytest.ini", "[pytest]\ntestpaths = tests\npythonpath = .\n")


# ============================================================================
# 1. E-Commerce Platform (demo_repos/ecommerce)
# ============================================================================

def setup_ecommerce_repo(target_dir: str) -> Dict[str, Any]:
    init_git_repo(target_dir)

    write_file(target_dir, "README.md", """# E-Commerce Platform
Domain model for shopping cart calculation, discounts, multi-tier bulk pricing,
and checkout payment calculations.
""")
    write_file(target_dir, "requirements.txt", "pytest>=7.4.0\nrequests==2.28.0\n")
    write_file(target_dir, "src/__init__.py", "")

    # src/cart.py
    write_file(target_dir, "src/cart.py", '''"""
src/cart.py — Shopping Cart Module
"""
from typing import List, Dict, Any

MAX_CART_ITEMS = 50


def calculate_cart_total(items: List[Dict[str, Any]]) -> float:
    """Calculates total price from cart items list."""
    if not isinstance(items, list):
        raise TypeError("Items must be a list")
    if len(items) > MAX_CART_ITEMS:
        raise ValueError(f"Cart exceeds maximum allowed limit of {MAX_CART_ITEMS} items")
    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("Item must be a dictionary")
        if "price" not in item:
            raise ValueError("Item missing required 'price' key")
        price = item["price"]
        qty = item.get("quantity", 1)
        if not isinstance(price, (int, float)) or not isinstance(qty, int):
            raise TypeError("Price and quantity must be numeric")
        if price < 0 or qty < 0:
            raise ValueError("Price and quantity must be non-negative")
        total += float(price * qty)
    return round(total, 2)


def apply_coupon(cart_total: float, coupon_code: str) -> float:
    """Applies valid discount coupon to cart total."""
    if not isinstance(cart_total, (int, float)):
        raise TypeError("Cart total must be numeric")
    if cart_total < 0:
        raise ValueError("Cart total cannot be negative")
    code = (coupon_code or "").strip().upper()
    if code == "SAVE10":
        return round(cart_total * 0.90, 2)
    elif code == "SAVE20":
        return round(cart_total * 0.80, 2)
    elif code == "HALFPRICE":
        return round(cart_total * 0.50, 2)
    return round(float(cart_total), 2)
''')

    # src/checkout.py (explicitly imports src.cart for AST dependency proof)
    write_file(target_dir, "src/checkout.py", '''"""
src/checkout.py — Checkout & Payment Module
Imports src.cart.calculate_cart_total for order processing.
"""
from typing import List, Dict, Any
from src.cart import calculate_cart_total


def apply_tax(amount: float, tax_rate: float) -> float:
    """Calculates amount including tax, rounded strictly to 2 decimal places."""
    if not isinstance(amount, (int, float)) or not isinstance(tax_rate, (int, float)):
        raise TypeError("Amount and tax rate must be numeric")
    if amount < 0 or tax_rate < 0:
        raise ValueError("Amount and tax rate cannot be negative")
    return round(amount * (1.0 + tax_rate), 2)


def calculate_order_final(subtotal: float, tax_rate: float, shipping_fee: float) -> float:
    """Calculates final order cost including tax and shipping."""
    taxed = apply_tax(subtotal, tax_rate)
    return round(taxed + shipping_fee, 2)


def checkout_cart(items: List[Dict[str, Any]], tax_rate: float = 0.08, shipping_fee: float = 5.0) -> float:
    """Coordinates cart checkout using calculate_cart_total from cart.py."""
    subtotal = calculate_cart_total(items)
    return calculate_order_final(subtotal, tax_rate, shipping_fee)


def validate_shipping_address(addr: Dict[str, Any]) -> bool:
    """Validates shipping address completeness."""
    if not isinstance(addr, dict):
        return False
    required = ["street", "city", "postal_code", "country"]
    return all(bool(addr.get(k)) for k in required)
''')

    # src/pricing.py
    write_file(target_dir, "src/pricing.py", '''"""
src/pricing.py — Pricing Rules & Bulk Discount Engine
"""
from typing import Dict, Any


def calculate_bulk_discount(quantity: int, unit_price: float) -> float:
    """Calculates volume pricing discounts for bulk purchasing."""
    if not isinstance(quantity, int) or not isinstance(unit_price, (int, float)):
        raise TypeError("Quantity and unit price must be numbers")
    if quantity < 0 or unit_price < 0:
        raise ValueError("Quantity and unit price must be positive")
    total = quantity * unit_price
    if quantity >= 100:
        return round(total * 0.70, 2)  # 30% off
    elif quantity >= 50:
        return round(total * 0.75, 2)  # 25% off
    elif quantity >= 20:
        return round(total * 0.85, 2)  # 15% off
    elif quantity >= 10:
        return round(total * 0.90, 2)  # 10% off
    return round(float(total), 2)


def format_currency(amount: float, symbol: str = "$") -> str:
    """Formats numeric amount into display currency string."""
    return f"{symbol}{amount:,.2f}"
''')

    # src/inventory.py
    write_file(target_dir, "src/inventory.py", '''"""
src/inventory.py — Warehouse Stock & Item Allocation
"""
from typing import Dict


def check_stock_level(stock_registry: Dict[str, int], sku: str, requested_qty: int) -> bool:
    """Checks whether warehouse has sufficient stock for an SKU."""
    if requested_qty <= 0:
        raise ValueError("Requested quantity must be positive")
    available = stock_registry.get(sku, 0)
    return available >= requested_qty


def deduct_stock(stock_registry: Dict[str, int], sku: str, quantity: int) -> int:
    """Deducts reserved stock and returns remaining units."""
    if not check_stock_level(stock_registry, sku, quantity):
        raise ValueError(f"Insufficient stock for SKU {sku}")
    stock_registry[sku] -= quantity
    return stock_registry[sku]


def is_low_stock_warning(current_units: int, threshold: int = 5) -> bool:
    """Flags items needing reordering."""
    return 0 < current_units <= threshold
''')

    # tests/__init__.py
    write_file(target_dir, "tests/__init__.py", "")

    # tests/test_cart.py (11 tests)
    write_file(target_dir, "tests/test_cart.py", '''"""
tests/test_cart.py
Unit tests for src/cart.py (11 test cases)
"""
import pytest
from src.cart import calculate_cart_total, apply_coupon


def test_calculate_cart_total_empty():
    assert calculate_cart_total([]) == 0.0


def test_calculate_cart_total_single_item():
    items = [{"price": 19.99, "quantity": 1}]
    assert calculate_cart_total(items) == 19.99


def test_calculate_cart_total_multiple_quantities():
    items = [{"price": 10.00, "quantity": 2}, {"price": 5.50, "quantity": 3}]
    assert calculate_cart_total(items) == 36.50


def test_calculate_cart_total_default_quantity():
    items = [{"price": 15.00}]
    assert calculate_cart_total(items) == 15.00


def test_calculate_cart_total_invalid_type():
    with pytest.raises(TypeError):
        calculate_cart_total("invalid")


def test_calculate_cart_total_missing_price():
    with pytest.raises(ValueError):
        calculate_cart_total([{"qty": 1}])


def test_calculate_cart_total_exceeds_max_limit():
    items = [{"price": 1.0}] * 51
    with pytest.raises(ValueError, match="maximum allowed limit"):
        calculate_cart_total(items)


def test_apply_coupon_save10():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_save20():
    assert apply_coupon(50.0, "SAVE20") == 40.0


def test_apply_coupon_halfprice():
    assert apply_coupon(80.0, "HALFPRICE") == 40.0


def test_apply_coupon_negative_total():
    with pytest.raises(ValueError):
        apply_coupon(-10.0, "SAVE10")
''')

    # tests/test_checkout.py (9 tests)
    write_file(target_dir, "tests/test_checkout.py", '''"""
tests/test_checkout.py
Unit tests for src/checkout.py (9 test cases)
"""
import pytest
from src.checkout import (
    apply_tax,
    calculate_order_final,
    checkout_cart,
    validate_shipping_address
)


def test_apply_tax_standard():
    assert apply_tax(100.0, 0.05) == 105.0


def test_apply_tax_zero_rate():
    assert apply_tax(50.0, 0.0) == 50.0


def test_apply_tax_fractional_precision():
    """
    CRITICAL PRECISION TEST:
    10.55 * 1.08 = 11.394 -> must strictly round to 11.39!
    Seeded checkout regression deliberately truncates to 11.0, failing this test!
    """
    assert apply_tax(10.55, 0.08) == 11.39


def test_apply_tax_negative_amount():
    with pytest.raises(ValueError):
        apply_tax(-10.0, 0.05)


def test_apply_tax_negative_rate():
    with pytest.raises(ValueError):
        apply_tax(100.0, -0.05)


def test_calculate_order_final_standard():
    assert calculate_order_final(100.0, 0.10, 5.0) == 115.0


def test_checkout_cart_integration():
    items = [{"price": 20.0, "quantity": 2}]
    # Subtotal: 40.0, Tax 10% (4.0) -> 44.0 + Shipping 5.0 -> 49.0
    assert checkout_cart(items, tax_rate=0.10, shipping_fee=5.0) == 49.0


def test_validate_shipping_address_valid():
    addr = {"street": "123 Tech Way", "city": "New Delhi", "postal_code": "110020", "country": "India"}
    assert validate_shipping_address(addr) is True


def test_validate_shipping_address_missing_field():
    addr = {"street": "123 Tech Way", "city": "New Delhi"}
    assert validate_shipping_address(addr) is False
''')

    # tests/test_pricing.py (6 tests)
    write_file(target_dir, "tests/test_pricing.py", '''"""
tests/test_pricing.py
Unit tests for src/pricing.py (6 test cases)
"""
import pytest
from src.pricing import calculate_bulk_discount, format_currency


def test_bulk_discount_under_threshold():
    assert calculate_bulk_discount(5, 10.0) == 50.0


def test_bulk_discount_tier_10():
    assert calculate_bulk_discount(10, 10.0) == 90.0


def test_bulk_discount_tier_20():
    assert calculate_bulk_discount(20, 10.0) == 170.0


def test_bulk_discount_tier_50():
    assert calculate_bulk_discount(50, 10.0) == 375.0


def test_format_currency_usd():
    assert format_currency(1234.50) == "$1,234.50"


def test_format_currency_inr():
    assert format_currency(500.0, symbol="₹") == "₹500.00"
''')

    # tests/test_inventory.py (6 tests)
    write_file(target_dir, "tests/test_inventory.py", '''"""
tests/test_inventory.py
Unit tests for src/inventory.py (6 test cases)
"""
import pytest
from src.inventory import check_stock_level, deduct_stock, is_low_stock_warning


def test_check_stock_level_sufficient():
    stock = {"SKU-A": 10, "SKU-B": 5}
    assert check_stock_level(stock, "SKU-A", 4) is True


def test_check_stock_level_insufficient():
    stock = {"SKU-A": 2}
    assert check_stock_level(stock, "SKU-A", 5) is False


def test_check_stock_level_negative_requested():
    with pytest.raises(ValueError):
        check_stock_level({"SKU-A": 5}, "SKU-A", -1)


def test_deduct_stock_success():
    stock = {"SKU-A": 10}
    remaining = deduct_stock(stock, "SKU-A", 3)
    assert remaining == 7
    assert stock["SKU-A"] == 7


def test_deduct_stock_overdraw_raises_error():
    stock = {"SKU-A": 2}
    with pytest.raises(ValueError, match="Insufficient stock"):
        deduct_stock(stock, "SKU-A", 5)


def test_is_low_stock_warning():
    assert is_low_stock_warning(3, threshold=5) is True
    assert is_low_stock_warning(10, threshold=5) is False
''')

    # Commit baseline
    run_git(["add", "."], cwd=target_dir)
    run_git(["commit", "-m", "Initial commit: Core platform and comprehensive test suite"], cwd=target_dir)
    base_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "base"], cwd=target_dir)

    # Branch 1: feature/cart-enhancement
    run_git(["checkout", "-b", "feature/cart-enhancement"], cwd=target_dir)
    write_file(target_dir, "src/cart.py", """# Enhanced cart with audit comments
from typing import List, Dict, Any

MAX_CART_ITEMS = 60


def calculate_cart_total(items: List[Dict[str, Any]]) -> float:
    \"\"\"Calculates total price from cart items list with expanded 60-item cap.\"\"\"
    if not isinstance(items, list):
        raise TypeError("Items must be a list")
    if len(items) > MAX_CART_ITEMS:
        raise ValueError(f"Cart exceeds maximum allowed limit of {MAX_CART_ITEMS} items")
    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("Item must be a dictionary")
        if "price" not in item:
            raise ValueError("Item missing required 'price' key")
        price = item["price"]
        qty = item.get("quantity", 1)
        if not isinstance(price, (int, float)) or not isinstance(qty, int):
            raise TypeError("Price and quantity must be numeric")
        if price < 0 or qty < 0:
            raise ValueError("Price and quantity must be non-negative")
        total += float(price * qty)
    return round(total, 2)


def apply_coupon(cart_total: float, coupon_code: str) -> float:
    if not isinstance(cart_total, (int, float)):
        raise TypeError("Cart total must be numeric")
    if cart_total < 0:
        raise ValueError("Cart total cannot be negative")
    code = (coupon_code or "").strip().upper()
    if code == "SAVE10":
        return round(cart_total * 0.90, 2)
    elif code == "SAVE20":
        return round(cart_total * 0.80, 2)
    elif code == "HALFPRICE":
        return round(cart_total * 0.50, 2)
    return round(float(cart_total), 2)
""")
    cart_test_enhancement = '''import pytest
from src.cart import calculate_cart_total, apply_coupon


def test_calculate_cart_total_empty():
    assert calculate_cart_total([]) == 0.0


def test_calculate_cart_total_single_item():
    items = [{"price": 25.50, "quantity": 1}]
    assert calculate_cart_total(items) == 25.50


def test_calculate_cart_total_multiple_quantities():
    items = [
        {"price": 10.0, "quantity": 2},
        {"price": 5.50, "quantity": 3}
    ]
    assert calculate_cart_total(items) == 36.50


def test_calculate_cart_total_default_quantity():
    items = [{"price": 15.0}]
    assert calculate_cart_total(items) == 15.0


def test_calculate_cart_total_invalid_type():
    with pytest.raises(TypeError):
        calculate_cart_total("invalid")


def test_calculate_cart_total_missing_price():
    with pytest.raises(ValueError):
        calculate_cart_total([{"qty": 1}])


def test_calculate_cart_total_exceeds_max_limit():
    # In enhanced cart, limit is 60 items, so 61 items exceeds the limit
    items = [{"price": 1.0}] * 61
    with pytest.raises(ValueError, match="maximum allowed limit"):
        calculate_cart_total(items)


def test_calculate_cart_total_at_expanded_limit_passes():
    # 60 items is within the new expanded capacity
    items = [{"price": 1.0}] * 60
    assert calculate_cart_total(items) == 60.0


def test_apply_coupon_save10():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_save20():
    assert apply_coupon(50.0, "SAVE20") == 40.0


def test_apply_coupon_halfprice():
    assert apply_coupon(80.0, "HALFPRICE") == 40.0


def test_apply_coupon_negative_total():
    with pytest.raises(ValueError):
        apply_coupon(-10.0, "SAVE10")
'''
    write_file(target_dir, "tests/test_cart.py", cart_test_enhancement)
    run_git(["add", "src/cart.py", "tests/test_cart.py"], cwd=target_dir)
    run_git(["commit", "-m", "feat(cart): expand max cart items cap to 60 with matching tests"], cwd=target_dir)
    cart_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "cart-enhancement"], cwd=target_dir)

    # Branch 2: regression/checkout-rounding-bug
    run_git(["checkout", "main"], cwd=target_dir)
    run_git(["checkout", "-b", "regression/checkout-rounding-bug"], cwd=target_dir)
    checkout_regression_code = '''"""
src/checkout.py — Checkout & Payment Module (WITH INTENTIONAL REGRESSION)
"""
from typing import List, Dict, Any
from src.cart import calculate_cart_total


def apply_tax(amount: float, tax_rate: float) -> float:
    """
    Calculates amount including tax.
    REGRESSION: Integer truncation causes loss of fractional cents!
    """
    if not isinstance(amount, (int, float)) or not isinstance(tax_rate, (int, float)):
        raise TypeError("Amount and tax rate must be numeric")
    if amount < 0 or tax_rate < 0:
        raise ValueError("Amount and tax rate cannot be negative")
    # INTRODUCED BUG: Truncates decimal cents! (e.g. 11.39 becomes 11.0)
    return float(int(amount * (1.0 + tax_rate)))


def calculate_order_final(subtotal: float, tax_rate: float, shipping_fee: float) -> float:
    taxed = apply_tax(subtotal, tax_rate)
    return round(taxed + shipping_fee, 2)


def checkout_cart(items: List[Dict[str, Any]], tax_rate: float = 0.08, shipping_fee: float = 5.0) -> float:
    subtotal = calculate_cart_total(items)
    return calculate_order_final(subtotal, tax_rate, shipping_fee)


def validate_shipping_address(addr: Dict[str, Any]) -> bool:
    if not isinstance(addr, dict):
        return False
    required = ["street", "city", "postal_code", "country"]
    return all(bool(addr.get(k)) for k in required)
'''
    write_file(target_dir, "src/checkout.py", checkout_regression_code)
    run_git(["add", "src/checkout.py"], cwd=target_dir)
    run_git(["commit", "-m", "refactor(checkout): optimize currency calculations (introduces regression)"], cwd=target_dir)
    checkout_bug_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "checkout-regression"], cwd=target_dir)

    # Branch 3: regression/cart-limit-bug
    run_git(["checkout", "main"], cwd=target_dir)
    run_git(["checkout", "-b", "regression/cart-limit-bug"], cwd=target_dir)
    cart_limit_regression_code = '''"""
src/cart.py — Shopping Cart Module (WITH INTENTIONAL LIMIT REGRESSION)
"""
from typing import List, Dict, Any

MAX_CART_ITEMS = 50


def calculate_cart_total(items: List[Dict[str, Any]]) -> float:
    """Calculates total price from cart items list."""
    if not isinstance(items, list):
        raise TypeError("Items must be a list")
    # INTENTIONAL REGRESSION BUG: Erroneously checks > 1000 instead of MAX_CART_ITEMS (50)
    # Fails to enforce the 50-item limit, allowing oversized carts to pass!
    if len(items) > 1000:
        raise ValueError(f"Cart exceeds maximum allowed limit of {MAX_CART_ITEMS} items")
    total = 0.0
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("Item must be a dictionary")
        if "price" not in item:
            raise ValueError("Item missing required 'price' key")
        price = item["price"]
        qty = item.get("quantity", 1)
        if not isinstance(price, (int, float)) or not isinstance(qty, int):
            raise TypeError("Price and quantity must be numeric")
        if price < 0 or qty < 0:
            raise ValueError("Price and quantity must be non-negative")
        total += float(price * qty)
    return round(total, 2)


def apply_coupon(cart_total: float, coupon_code: str) -> float:
    """Applies valid discount coupon to cart total."""
    if not isinstance(cart_total, (int, float)):
        raise TypeError("Cart total must be numeric")
    if cart_total < 0:
        raise ValueError("Cart total cannot be negative")
    code = (coupon_code or "").strip().upper()
    if code == "SAVE10":
        return round(cart_total * 0.90, 2)
    elif code == "SAVE20":
        return round(cart_total * 0.80, 2)
    elif code == "HALFPRICE":
        return round(cart_total * 0.50, 2)
    return round(float(cart_total), 2)
'''
    write_file(target_dir, "src/cart.py", cart_limit_regression_code)
    run_git(["add", "src/cart.py"], cwd=target_dir)
    run_git(["commit", "-m", "fix(cart): update items check logic (introduces limit regression)"], cwd=target_dir)
    cart_limit_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "cart-limit-regression"], cwd=target_dir)

    # Reset back to main
    run_git(["checkout", "main"], cwd=target_dir)

    scenarios = [
        {
            "id": "cart_enhancement",
            "title": "Scenario 1: Cart Enhancement (Healthy PR)",
            "description": "Increases cart items limit to 60. Validates 100% pass rate across entire suite.",
            "base_ref": "base",
            "target_ref": "cart-enhancement",
            "base_commit": base_commit,
            "target_commit": cart_commit,
            "is_regression": False,
            "expected_changed_files": ["src/cart.py"],
            "expected_top_test": "tests/test_cart.py",
            "expected_pass_rate": 1.0,
            "notes": "Verified 100% healthy feature PR; all tests pass."
        },
        {
            "id": "checkout_regression",
            "title": "Scenario 2: Currency Rounding Regression (Authentic Failing Demo)",
            "description": "Integer truncation in apply_tax causes precision loss on fractional cents. In standard mode, fails at test #14; in prioritized mode, catches failure at test #3.",
            "base_ref": "base",
            "target_ref": "checkout-regression",
            "base_commit": base_commit,
            "target_commit": checkout_bug_commit,
            "is_regression": True,
            "expected_changed_files": ["src/checkout.py"],
            "expected_top_test": "tests/test_checkout.py",
            "detecting_test": "tests/test_checkout.py::test_apply_tax_fractional_precision",
            "regression_details": {
                "intended_behavior": "apply_tax(10.55, 0.08) rounds 11.394 to 11.39",
                "introduced_regression": "apply_tax uses float(int(amount * (1.0 + tax_rate))) which truncates 11.394 to 11.0",
                "detecting_test": "tests/test_checkout.py::test_apply_tax_fractional_precision",
                "expected_outcome": "11.39",
                "observed_outcome": "11.0"
            },
            "notes": "Authentic failing regression in checkout domain."
        },
        {
            "id": "cart_limit_regression",
            "title": "Scenario 3: Cart Capacity Limit Bug (Failing Cart Bug)",
            "description": "Lenient condition in calculate_cart_total bypasses 50-item limit. Prioritizes test_cart.py directly to catch failure immediately.",
            "base_ref": "base",
            "target_ref": "cart-limit-regression",
            "base_commit": base_commit,
            "target_commit": cart_limit_commit,
            "is_regression": True,
            "expected_changed_files": ["src/cart.py"],
            "expected_top_test": "tests/test_cart.py",
            "detecting_test": "tests/test_cart.py::test_calculate_cart_total_exceeds_max_limit",
            "regression_details": {
                "intended_behavior": "calculate_cart_total with 51 items raises ValueError(maximum allowed limit of 50 items)",
                "introduced_regression": "Condition checked len(items) > 1000, failing to reject oversized carts",
                "detecting_test": "tests/test_cart.py::test_calculate_cart_total_exceeds_max_limit",
                "expected_outcome": "ValueError",
                "observed_outcome": "No Exception (Silent Pass)"
            },
            "notes": "Authentic failing regression in cart domain."
        },
        {
            "id": "checkout_cart_dependency",
            "title": "Scenario 4: Checkout -> Cart AST Dependency Proof",
            "description": "src/checkout.py imports src/cart.py. Modifying checkout maps both test_checkout.py (direct) and test_cart.py (upstream dependency).",
            "base_ref": "base",
            "target_ref": "checkout-regression",
            "base_commit": base_commit,
            "target_commit": checkout_bug_commit,
            "is_regression": True,
            "expected_changed_files": ["src/checkout.py"],
            "expected_top_test": "tests/test_checkout.py",
            "notes": "Dedicated proof scenario for bidirectional AST dependency mapping."
        }
    ]

    manifest_path = os.path.join(target_dir, "scenarios.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2)
    run_git(["add", "scenarios.json"], cwd=target_dir)
    run_git(["commit", "-m", "docs: add scenarios manifest"], cwd=target_dir)

    return {"repo_id": "ecommerce", "repo_path": target_dir, "test_count": 32, "scenarios": scenarios}


# ============================================================================
# 2. Authentication Service (demo_repos/auth_service)
# ============================================================================

def setup_auth_service_repo(target_dir: str) -> Dict[str, Any]:
    init_git_repo(target_dir)

    write_file(target_dir, "README.md", """# Authentication & Access Control Service
User authentication, token issuance, password validation, and permission checks.
""")
    write_file(target_dir, "requirements.txt", "pytest>=7.4.0\n")
    write_file(target_dir, "src/__init__.py", "")

    # src/token_service.py
    write_file(target_dir, "src/token_service.py", '''"""
src/token_service.py — Token Issuance & Signature Verification
"""
import hashlib
import time


def generate_token(user_id: str, secret_key: str = "demo-secret") -> str:
    """Generates deterministic pseudo-JWT token for user."""
    if not user_id:
        raise ValueError("user_id cannot be empty")
    payload = f"{user_id}:{secret_key}:v1"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"tk_{user_id}_{digest[:16]}"


def verify_token(token: str, secret_key: str = "demo-secret") -> bool:
    """Verifies token structure and cryptographic digest."""
    if not token or not token.startswith("tk_"):
        return False
    parts = token.split("_")
    if len(parts) != 3:
        return False
    user_id, digest = parts[1], parts[2]
    expected = generate_token(user_id, secret_key)
    return token == expected
''')

    # src/password_hasher.py
    write_file(target_dir, "src/password_hasher.py", '''"""
src/password_hasher.py — Password Hashing & Strength Checking
"""
import hashlib


def hash_password(password: str, salt: str = "fixed_salt_demo") -> str:
    """Hashes password with SHA-256 and salt."""
    if len(password) < 6:
        raise ValueError("Password must have at least 6 characters")
    combined = f"{salt}:{password}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def verify_password_strength(password: str) -> bool:
    """Checks for length, digits, and mixed case."""
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    return has_digit and has_upper
''')

    # src/permissions.py
    write_file(target_dir, "src/permissions.py", '''"""
src/permissions.py — Role-Based Access Control (RBAC) Engine
"""
ROLE_PERMISSIONS = {
    "admin": {"user:read", "user:write", "system:admin"},
    "editor": {"user:read", "user:write"},
    "viewer": {"user:read"},
    "guest": set()
}


def check_permission(role: str, permission: str) -> bool:
    """Evaluates whether given role has permission."""
    allowed = ROLE_PERMISSIONS.get(role, set())
    return permission in allowed


def get_role_hierarchy(role: str) -> int:
    """Returns integer privilege level."""
    levels = {"admin": 100, "editor": 50, "viewer": 10, "guest": 0}
    return levels.get(role, 0)
''')

    # src/auth.py (imports token_service and password_hasher)
    write_file(target_dir, "src/auth.py", '''"""
src/auth.py — Authentication Orchestration Service
Imports token_service and password_hasher.
"""
from src.token_service import generate_token, verify_token
from src.password_hasher import hash_password, verify_password_strength


def authenticate_user(username: str, password_hash: str, user_db: dict) -> dict:
    """Validates user password hash and returns session token."""
    if not username or username not in user_db:
        return {"authenticated": False, "token": None}
    stored_hash = user_db[username]
    if stored_hash != password_hash:
        return {"authenticated": False, "token": None}
    token = generate_token(username)
    return {"authenticated": True, "token": token}


def register_user(username: str, plain_password: str) -> str:
    """Validates password strength and returns hash."""
    if not verify_password_strength(plain_password):
        raise ValueError("Password does not meet security requirements")
    return hash_password(plain_password)
''')

    write_file(target_dir, "tests/__init__.py", "")

    # tests/test_token_service.py (4 tests)
    write_file(target_dir, "tests/test_token_service.py", '''
import pytest
from src.token_service import generate_token, verify_token


def test_generate_token_structure():
    t = generate_token("alice")
    assert t.startswith("tk_alice_")


def test_generate_token_empty_user_raises():
    with pytest.raises(ValueError):
        generate_token("")


def test_verify_token_valid():
    t = generate_token("bob")
    assert verify_token(t) is True


def test_verify_token_invalid():
    assert verify_token("invalid_token_string") is False
''')

    # tests/test_password_hasher.py (4 tests)
    write_file(target_dir, "tests/test_password_hasher.py", '''
import pytest
from src.password_hasher import hash_password, verify_password_strength


def test_hash_password_length():
    h = hash_password("secret123")
    assert len(h) == 64


def test_hash_password_too_short():
    with pytest.raises(ValueError):
        hash_password("123")


def test_verify_password_strength_strong():
    assert verify_password_strength("ValidPass1") is True


def test_verify_password_strength_weak():
    assert verify_password_strength("simple") is False
''')

    # tests/test_permissions.py (4 tests)
    write_file(target_dir, "tests/test_permissions.py", '''
import pytest
from src.permissions import check_permission, get_role_hierarchy


def test_admin_has_system_admin():
    assert check_permission("admin", "system:admin") is True


def test_viewer_cannot_write():
    assert check_permission("viewer", "user:write") is False


def test_guest_has_no_permissions():
    """
    CRITICAL ACCESS TEST:
    Ensures guest cannot perform system:admin actions.
    Seeded permissions regression returns True here!
    """
    assert check_permission("guest", "system:admin") is False


def test_role_hierarchy_admin_greater():
    assert get_role_hierarchy("admin") > get_role_hierarchy("viewer")
''')

    # tests/test_auth.py (5 tests)
    write_file(target_dir, "tests/test_auth.py", '''
import pytest
from src.auth import authenticate_user, register_user
from src.password_hasher import hash_password


def test_authenticate_user_success():
    db = {"alice": hash_password("Password123")}
    res = authenticate_user("alice", hash_password("Password123"), db)
    assert res["authenticated"] is True
    assert res["token"].startswith("tk_alice_")


def test_authenticate_user_bad_password():
    db = {"alice": hash_password("Password123")}
    res = authenticate_user("alice", hash_password("WrongPassword"), db)
    assert res["authenticated"] is False


def test_authenticate_user_unknown_user():
    res = authenticate_user("unknown", "hash", {})
    assert res["authenticated"] is False


def test_register_user_success():
    h = register_user("bob", "StrongPass1")
    assert len(h) == 64


def test_register_user_weak_password():
    with pytest.raises(ValueError):
        register_user("bob", "weak")
''')

    # Commit baseline
    run_git(["add", "."], cwd=target_dir)
    run_git(["commit", "-m", "Initial commit: Auth service baseline"], cwd=target_dir)
    base_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "base"], cwd=target_dir)

    # Regression: permissions bypass in src/permissions.py
    run_git(["checkout", "-b", "regression/permissions-bypass"], cwd=target_dir)
    permissions_bug_code = '''"""
src/permissions.py — Role-Based Access Control (WITH PERMISSION BYPASS BUG)
"""
ROLE_PERMISSIONS = {
    "admin": {"user:read", "user:write", "system:admin"},
    "editor": {"user:read", "user:write"},
    "viewer": {"user:read"},
    "guest": set()
}


def check_permission(role: str, permission: str) -> bool:
    # REGRESSION BUG: Improper default check returns True for guest role!
    if role == "guest":
        return True
    allowed = ROLE_PERMISSIONS.get(role, set())
    return permission in allowed


def get_role_hierarchy(role: str) -> int:
    levels = {"admin": 100, "editor": 50, "viewer": 10, "guest": 0}
    return levels.get(role, 0)
'''
    write_file(target_dir, "src/permissions.py", permissions_bug_code)
    run_git(["add", "src/permissions.py"], cwd=target_dir)
    run_git(["commit", "-m", "refactor(permissions): relax guest checks (introduces regression)"], cwd=target_dir)
    bug_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "permissions-bypass"], cwd=target_dir)

    run_git(["checkout", "main"], cwd=target_dir)

    scenarios = [
        {
            "id": "permissions_bypass",
            "title": "Scenario: RBAC Privilege Escalation Regression",
            "description": "Seeded bug in src/permissions.py allows guest role to bypass authorization. Caught at test #10 in standard mode; caught at test #2 in prioritized mode.",
            "base_ref": "base",
            "target_ref": "permissions-bypass",
            "base_commit": base_commit,
            "target_commit": bug_commit,
            "is_regression": True,
            "expected_changed_files": ["src/permissions.py"],
            "expected_top_test": "tests/test_permissions.py",
            "detecting_test": "tests/test_permissions.py::test_guest_has_no_permissions",
            "notes": "Authentic permissions failure."
        },
        {
            "id": "auth_token_dependency",
            "title": "Scenario: Auth -> Token Service AST Dependency Proof",
            "description": "src/auth.py imports src/token_service.py. Modifying auth maps both test_auth.py (direct) and test_token_service.py (upstream dependency).",
            "base_ref": "base",
            "target_ref": "permissions-bypass",
            "base_commit": base_commit,
            "target_commit": bug_commit,
            "is_regression": False,
            "expected_changed_files": ["src/auth.py"],
            "expected_top_test": "tests/test_auth.py",
            "notes": "Demonstrates AST upstream dependency matching in Auth domain."
        }
    ]

    write_file(target_dir, "scenarios.json", json.dumps(scenarios, indent=2))
    run_git(["add", "scenarios.json"], cwd=target_dir)
    run_git(["commit", "-m", "docs: add scenarios manifest"], cwd=target_dir)
    return {"repo_id": "auth_service", "repo_path": target_dir, "test_count": 17, "scenarios": scenarios}


# ============================================================================
# 3. Payment Gateway (demo_repos/payment_gateway)
# ============================================================================

def setup_payment_gateway_repo(target_dir: str) -> Dict[str, Any]:
    init_git_repo(target_dir)

    write_file(target_dir, "README.md", """# Payment Processing Gateway
Payment transactions, credit card validation, invoicing, and refunds.
""")
    write_file(target_dir, "requirements.txt", "pytest>=7.4.0\n")
    write_file(target_dir, "src/__init__.py", "")

    # src/card_validator.py
    write_file(target_dir, "src/card_validator.py", '''"""
src/card_validator.py — Credit Card Format & Luhn Check
"""
def luhn_checksum(card_number: str) -> bool:
    """Validates credit card number with Luhn algorithm."""
    clean = "".join(filter(str.isdigit, card_number))
    if len(clean) < 13 or len(clean) > 19:
        return False
    digits = [int(d) for d in clean]
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


def detect_card_brand(card_number: str) -> str:
    """Identifies card network from prefix."""
    clean = "".join(filter(str.isdigit, card_number))
    if clean.startswith("4"):
        return "VISA"
    elif clean.startswith(("51", "52", "53", "54", "55")):
        return "MASTERCARD"
    elif clean.startswith(("34", "37")):
        return "AMEX"
    return "UNKNOWN"
''')

    # src/invoice.py
    write_file(target_dir, "src/invoice.py", '''"""
src/invoice.py — Invoice Computation
"""
def calculate_invoice_total(line_items: list, vat_rate: float = 0.20) -> float:
    """Computes total cost plus VAT."""
    if not isinstance(line_items, list):
        raise TypeError("Line items must be a list")
    subtotal = sum(item.get("amount", 0.0) for item in line_items)
    return round(subtotal * (1.0 + vat_rate), 2)


def generate_invoice_id(sequence_num: int) -> str:
    """Formats 6-digit invoice identifier."""
    if sequence_num < 1:
        raise ValueError("Sequence number must be positive")
    return f"INV-{sequence_num:06d}"
''')

    # src/refund.py
    write_file(target_dir, "src/refund.py", '''"""
src/refund.py — Refund Rules & Validation
"""
def is_eligible_for_refund(days_since_purchase: int, max_window: int = 30) -> bool:
    """Refunds are valid strictly within the 30-day window."""
    if days_since_purchase < 0:
        raise ValueError("Days cannot be negative")
    # Correct implementation: must be <= max_window
    return days_since_purchase <= max_window


def calculate_partial_refund(original_amount: float, refund_ratio: float) -> float:
    """Calculates partial refund amount."""
    if original_amount <= 0 or not (0.0 < refund_ratio <= 1.0):
        raise ValueError("Invalid refund parameters")
    return round(original_amount * refund_ratio, 2)
''')

    # src/payment.py (imports card_validator and invoice)
    write_file(target_dir, "src/payment.py", '''"""
src/payment.py — Payment Charge Engine
Imports card_validator and invoice.
"""
from src.card_validator import luhn_checksum, detect_card_brand
from src.invoice import calculate_invoice_total


def authorize_payment(card_number: str, amount: float) -> dict:
    """Validates card and authorizes monetary amount."""
    if amount <= 0:
        return {"authorized": False, "reason": "Non-positive amount"}
    if not luhn_checksum(card_number):
        return {"authorized": False, "reason": "Invalid card checksum"}
    brand = detect_card_brand(card_number)
    return {"authorized": True, "brand": brand, "amount": amount}


def process_order_charge(card_number: str, line_items: list) -> dict:
    """Computes invoice total and authorizes payment."""
    total = calculate_invoice_total(line_items)
    return authorize_payment(card_number, total)
''')

    write_file(target_dir, "tests/__init__.py", "")

    # tests/test_card_validator.py (4 tests)
    write_file(target_dir, "tests/test_card_validator.py", '''
import pytest
from src.card_validator import luhn_checksum, detect_card_brand


def test_luhn_valid_visa():
    # 4532015112830366 is a valid 16-digit Luhn test number
    assert luhn_checksum("4532015112830366") is True


def test_luhn_invalid():
    assert luhn_checksum("4532015112830367") is False


def test_detect_brand_visa():
    assert detect_card_brand("4111111111111") == "VISA"


def test_detect_brand_mastercard():
    assert detect_card_brand("5105105105105100") == "MASTERCARD"
''')

    # tests/test_invoice.py (4 tests)
    write_file(target_dir, "tests/test_invoice.py", '''
import pytest
from src.invoice import calculate_invoice_total, generate_invoice_id


def test_calculate_invoice_total_standard():
    items = [{"amount": 100.0}]
    assert calculate_invoice_total(items, 0.20) == 120.0


def test_calculate_invoice_total_empty():
    assert calculate_invoice_total([], 0.20) == 0.0


def test_generate_invoice_id_format():
    assert generate_invoice_id(42) == "INV-000042"


def test_generate_invoice_id_negative():
    with pytest.raises(ValueError):
        generate_invoice_id(-1)
''')

    # tests/test_payment.py (5 tests)
    write_file(target_dir, "tests/test_payment.py", '''
import pytest
from src.payment import authorize_payment, process_order_charge


def test_authorize_payment_success():
    res = authorize_payment("4532015112830366", 50.0)
    assert res["authorized"] is True
    assert res["brand"] == "VISA"


def test_authorize_payment_invalid_card():
    res = authorize_payment("1234567890", 50.0)
    assert res["authorized"] is False


def test_authorize_payment_negative_amount():
    res = authorize_payment("4532015112830366", -10.0)
    assert res["authorized"] is False


def test_process_order_charge_success():
    items = [{"amount": 50.0}, {"amount": 50.0}]
    # 100.0 + 20% vat = 120.0
    res = process_order_charge("4532015112830366", items)
    assert res["authorized"] is True
    assert res["amount"] == 120.0


def test_process_order_charge_invalid_card():
    res = process_order_charge("1234", [{"amount": 10.0}])
    assert res["authorized"] is False
''')

    # tests/test_refund.py (4 tests)
    write_file(target_dir, "tests/test_refund.py", '''
import pytest
from src.refund import is_eligible_for_refund, calculate_partial_refund


def test_refund_within_window():
    assert is_eligible_for_refund(14) is True


def test_refund_exact_window_boundary():
    assert is_eligible_for_refund(30) is True


def test_refund_outside_window_rejected():
    """
    CRITICAL POLICY TEST:
    Purchases older than 30 days must be strictly rejected!
    Seeded refund regression returns True for 45 days, failing this test!
    """
    assert is_eligible_for_refund(45) is False


def test_calculate_partial_refund():
    assert calculate_partial_refund(100.0, 0.5) == 50.0
''')

    run_git(["add", "."], cwd=target_dir)
    run_git(["commit", "-m", "Initial commit: Payment gateway baseline"], cwd=target_dir)
    base_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "base"], cwd=target_dir)

    # Regression: refund window bypass in src/refund.py
    run_git(["checkout", "-b", "regression/refund-window-bug"], cwd=target_dir)
    refund_bug_code = '''"""
src/refund.py — Refund Rules (WITH POLICY REGRESSION BUG)
"""
def is_eligible_for_refund(days_since_purchase: int, max_window: int = 30) -> bool:
    if days_since_purchase < 0:
        raise ValueError("Days cannot be negative")
    # INTENTIONAL BUG: Inverted logic or 90-day override permits expired refunds!
    return True


def calculate_partial_refund(original_amount: float, refund_ratio: float) -> float:
    if original_amount <= 0 or not (0.0 < refund_ratio <= 1.0):
        raise ValueError("Invalid refund parameters")
    return round(original_amount * refund_ratio, 2)
'''
    write_file(target_dir, "src/refund.py", refund_bug_code)
    run_git(["add", "src/refund.py"], cwd=target_dir)
    run_git(["commit", "-m", "refactor(refund): relax refund window (introduces regression)"], cwd=target_dir)
    bug_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "refund-window-bug"], cwd=target_dir)

    run_git(["checkout", "main"], cwd=target_dir)

    scenarios = [
        {
            "id": "refund_window_regression",
            "title": "Scenario: Refund Policy Expiration Regression",
            "description": "Seeded bug in src/refund.py allows refunds past 30 days. Fails test #15 in standard mode; catches failure at test #2 in prioritized mode.",
            "base_ref": "base",
            "target_ref": "refund-window-bug",
            "base_commit": base_commit,
            "target_commit": bug_commit,
            "is_regression": True,
            "expected_changed_files": ["src/refund.py"],
            "expected_top_test": "tests/test_refund.py",
            "detecting_test": "tests/test_refund.py::test_refund_outside_window_rejected",
            "notes": "Authentic refund policy violation."
        },
        {
            "id": "payment_card_dependency",
            "title": "Scenario: Payment -> Card Validator AST Dependency Proof",
            "description": "src/payment.py imports src/card_validator.py. Modifying payment maps both test_payment.py (direct) and test_card_validator.py (upstream dependency).",
            "base_ref": "base",
            "target_ref": "refund-window-bug",
            "base_commit": base_commit,
            "target_commit": bug_commit,
            "is_regression": False,
            "expected_changed_files": ["src/payment.py"],
            "expected_top_test": "tests/test_payment.py",
            "notes": "Demonstrates AST upstream dependency matching in Payment domain."
        }
    ]

    write_file(target_dir, "scenarios.json", json.dumps(scenarios, indent=2))
    run_git(["add", "scenarios.json"], cwd=target_dir)
    run_git(["commit", "-m", "docs: add scenarios manifest"], cwd=target_dir)
    return {"repo_id": "payment_gateway", "repo_path": target_dir, "test_count": 17, "scenarios": scenarios}


# ============================================================================
# 4. Booking Platform (demo_repos/booking_platform)
# ============================================================================

def setup_booking_platform_repo(target_dir: str) -> Dict[str, Any]:
    init_git_repo(target_dir)

    write_file(target_dir, "README.md", """# Appointment & Booking Platform
Calendar scheduling, slot availability, notifications, and reservations.
""")
    write_file(target_dir, "requirements.txt", "pytest>=7.4.0\n")
    write_file(target_dir, "src/__init__.py", "")

    # src/availability.py
    write_file(target_dir, "src/availability.py", '''"""
src/availability.py — Calendar Slot Availability
"""
def is_slot_available(booked_slots: set, target_hour: int) -> bool:
    """Checks whether 9am-5pm hour is open."""
    if not (9 <= target_hour <= 17):
        return False
    return target_hour not in booked_slots


def find_next_available_slot(booked_slots: set, preferred_hour: int = 9) -> int:
    """Finds first open slot starting from preferred_hour."""
    for h in range(max(9, preferred_hour), 18):
        if is_slot_available(booked_slots, h):
            return h
    return -1
''')

    # src/calendar_service.py
    write_file(target_dir, "src/calendar_service.py", '''"""
src/calendar_service.py — Calendar Event Utilities
"""
def format_event_title(client_name: str, service_type: str) -> str:
    """Formats calendar event summary."""
    if not client_name or not service_type:
        raise ValueError("Client and service required")
    return f"{service_type.upper()}: {client_name.strip()}"


def calculate_session_duration(start_hour: int, end_hour: int) -> int:
    """Calculates duration in minutes."""
    if end_hour <= start_hour:
        raise ValueError("End hour must be strictly after start hour")
    return (end_hour - start_hour) * 60
''')

    # src/notifications.py
    write_file(target_dir, "src/notifications.py", '''"""
src/notifications.py — Booking Confirmation & Notification Messages
"""
def format_confirmation(client_email: str, appointment_hour: int) -> str:
    """Formats customer confirmation email message."""
    if "@" not in client_email:
        raise ValueError("Invalid client email format")
    # Correct implementation:
    return f"Confirmed appointment for {client_email} at {appointment_hour}:00."


def should_send_reminder(hours_until_event: int) -> bool:
    """Triggers reminder at 24 hours."""
    return hours_until_event == 24
''')

    # src/booking.py (imports availability and notifications)
    write_file(target_dir, "src/booking.py", '''"""
src/booking.py — Booking Reservation Orchestration
Imports availability and notifications.
"""
from src.availability import is_slot_available
from src.notifications import format_confirmation


def book_appointment(booked_slots: set, client_email: str, hour: int) -> dict:
    """Reserves appointment slot and generates confirmation."""
    if not is_slot_available(booked_slots, hour):
        return {"success": False, "message": "Slot already taken"}
    booked_slots.add(hour)
    msg = format_confirmation(client_email, hour)
    return {"success": True, "slot": hour, "confirmation": msg}


def cancel_appointment(booked_slots: set, hour: int) -> bool:
    """Frees booked calendar slot."""
    if hour in booked_slots:
        booked_slots.remove(hour)
        return True
    return False
''')

    write_file(target_dir, "tests/__init__.py", "")

    # tests/test_availability.py (4 tests)
    write_file(target_dir, "tests/test_availability.py", '''
import pytest
from src.availability import is_slot_available, find_next_available_slot


def test_is_slot_available_open():
    assert is_slot_available(set(), 10) is True


def test_is_slot_available_taken():
    assert is_slot_available({10}, 10) is False


def test_is_slot_available_outside_hours():
    assert is_slot_available(set(), 20) is False


def test_find_next_available_slot():
    assert find_next_available_slot({9, 10}, preferred_hour=9) == 11
''')

    # tests/test_calendar_service.py (4 tests)
    write_file(target_dir, "tests/test_calendar_service.py", '''
import pytest
from src.calendar_service import format_event_title, calculate_session_duration


def test_format_event_title():
    assert format_event_title("John Doe", "Consultation") == "CONSULTATION: John Doe"


def test_format_event_title_missing():
    with pytest.raises(ValueError):
        format_event_title("", "Demo")


def test_calculate_session_duration():
    assert calculate_session_duration(9, 11) == 120


def test_calculate_session_duration_inverted():
    with pytest.raises(ValueError):
        calculate_session_duration(11, 9)
''')

    # tests/test_notifications.py (4 tests)
    write_file(target_dir, "tests/test_notifications.py", '''
import pytest
from src.notifications import format_confirmation, should_send_reminder


def test_format_confirmation_valid():
    msg = format_confirmation("user@example.com", 14)
    assert "user@example.com" in msg
    assert "14:00" in msg


def test_format_confirmation_invalid_email():
    with pytest.raises(ValueError):
        format_confirmation("invalid_email", 14)


def test_format_confirmation_message_structure():
    """
    CRITICAL MESSAGE CONTRACT:
    Ensures 'Confirmed appointment for' header is present.
    Seeded notifications regression crashes or corrupts this string!
    """
    msg = format_confirmation("user@example.com", 10)
    assert msg.startswith("Confirmed appointment for")


def test_should_send_reminder():
    assert should_send_reminder(24) is True
    assert should_send_reminder(12) is False
''')

    # tests/test_booking.py (5 tests)
    write_file(target_dir, "tests/test_booking.py", '''
import pytest
from src.booking import book_appointment, cancel_appointment


def test_book_appointment_success():
    slots = set()
    res = book_appointment(slots, "test@domain.com", 10)
    assert res["success"] is True
    assert 10 in slots


def test_book_appointment_conflict():
    slots = {10}
    res = book_appointment(slots, "test@domain.com", 10)
    assert res["success"] is False


def test_book_appointment_invalid_email():
    slots = set()
    with pytest.raises(ValueError):
        book_appointment(slots, "bad_email", 10)


def test_cancel_appointment_success():
    slots = {10}
    assert cancel_appointment(slots, 10) is True
    assert 10 not in slots


def test_cancel_appointment_nonexistent():
    slots = set()
    assert cancel_appointment(slots, 10) is False
''')

    run_git(["add", "."], cwd=target_dir)
    run_git(["commit", "-m", "Initial commit: Booking platform baseline"], cwd=target_dir)
    base_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "base"], cwd=target_dir)

    # Regression: notification formatting crash in src/notifications.py
    run_git(["checkout", "-b", "regression/notification-bug"], cwd=target_dir)
    notification_bug_code = '''"""
src/notifications.py — Booking Notifications (WITH REGRESSION BUG)
"""
def format_confirmation(client_email: str, appointment_hour: int) -> str:
    if "@" not in client_email:
        raise ValueError("Invalid client email format")
    # INTENTIONAL REGRESSION BUG: Missing header breaks contract!
    return f"BROKEN_ALERT: {client_email}"


def should_send_reminder(hours_until_event: int) -> bool:
    return hours_until_event == 24
'''
    write_file(target_dir, "src/notifications.py", notification_bug_code)
    run_git(["add", "src/notifications.py"], cwd=target_dir)
    run_git(["commit", "-m", "refactor(notifications): simplify alert text (introduces regression)"], cwd=target_dir)
    bug_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "notification-bug"], cwd=target_dir)

    run_git(["checkout", "main"], cwd=target_dir)

    scenarios = [
        {
            "id": "notifications_crash_regression",
            "title": "Scenario: Notification Format Contract Regression",
            "description": "Seeded bug in src/notifications.py corrupts confirmation structure. Fails at test #15 in standard mode; catches failure at test #2 in prioritized mode.",
            "base_ref": "base",
            "target_ref": "notification-bug",
            "base_commit": base_commit,
            "target_commit": bug_commit,
            "is_regression": True,
            "expected_changed_files": ["src/notifications.py"],
            "expected_top_test": "tests/test_notifications.py",
            "detecting_test": "tests/test_notifications.py::test_format_confirmation_message_structure",
            "notes": "Authentic notification contract violation."
        },
        {
            "id": "booking_availability_dependency",
            "title": "Scenario: Booking -> Availability AST Dependency Proof",
            "description": "src/booking.py imports src/availability.py. Modifying booking maps both test_booking.py (direct) and test_availability.py (upstream dependency).",
            "base_ref": "base",
            "target_ref": "notification-bug",
            "base_commit": base_commit,
            "target_commit": bug_commit,
            "is_regression": False,
            "expected_changed_files": ["src/booking.py"],
            "expected_top_test": "tests/test_booking.py",
            "notes": "Demonstrates AST upstream dependency matching in Booking domain."
        }
    ]

    write_file(target_dir, "scenarios.json", json.dumps(scenarios, indent=2))
    run_git(["add", "scenarios.json"], cwd=target_dir)
    run_git(["commit", "-m", "docs: add scenarios manifest"], cwd=target_dir)
    return {"repo_id": "booking_platform", "repo_path": target_dir, "test_count": 17, "scenarios": scenarios}


# ============================================================================
# Main Orchestrator
# ============================================================================

def setup_all_demo_repositories(root_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Builds all 4 demo repositories under demo_repos/ and synchronizes demo_repo."""
    target_root = os.path.abspath(root_dir) if root_dir else DEMO_REPOS_ROOT
    os.makedirs(target_root, exist_ok=True)

    ecom_dir = os.path.join(target_root, "ecommerce")
    auth_dir = os.path.join(target_root, "auth_service")
    pay_dir = os.path.join(target_root, "payment_gateway")
    book_dir = os.path.join(target_root, "booking_platform")

    print(f"Setting up Ecommerce Demo Repo in: {ecom_dir}")
    r1 = setup_ecommerce_repo(ecom_dir)

    print(f"Setting up Auth Service Demo Repo in: {auth_dir}")
    r2 = setup_auth_service_repo(auth_dir)

    print(f"Setting up Payment Gateway Demo Repo in: {pay_dir}")
    r3 = setup_payment_gateway_repo(pay_dir)

    print(f"Setting up Booking Platform Demo Repo in: {book_dir}")
    r4 = setup_booking_platform_repo(book_dir)

    # Sync legacy demo_repo for 100% backward compatibility
    print(f"Synchronizing legacy demo_repo in: {LEGACY_DEMO_REPO}")
    setup_ecommerce_repo(LEGACY_DEMO_REPO)

    return [r1, r2, r3, r4]


setup_all = setup_all_demo_repositories


if __name__ == "__main__":
    results = setup_all_demo_repositories()
    print("\nAll 4 demo repositories created successfully:")
    for r in results:
        print(f" - {r['repo_id']}: {r['test_count']} tests across {len(r['scenarios'])} scenarios in {r['repo_path']}")
