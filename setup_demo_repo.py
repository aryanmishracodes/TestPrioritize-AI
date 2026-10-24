"""
setup_demo_repo.py
Part of TestPrioritize AI.

Creates an isolated, reproducible Git repository under demo_repo/
with genuine commits, branches/tags, realistic source modules,
comprehensive pytest suites, and specific test scenarios:
1. Healthy Cart Calculation Enhancement
2. Intentional Checkout Rounding Regression (failing test demonstration)
3. Multi-Module Pricing & Cart Overhaul
4. Dependency Upgrade (requirements.txt modified for TinyFish demo)
"""

import json
import os
import shutil
import subprocess
import sys
from typing import Dict, Any, List

DEMO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "demo_repo"))


def run_git(args: List[str], cwd: str) -> str:
    """Safely runs a Git command in the demo repository."""
    cmd = ["git"] + args
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def write_file(base_path: str, rel_path: str, content: str) -> None:
    full_path = os.path.join(base_path, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)


def init_demo_repository(target_dir: str = DEMO_DIR) -> Dict[str, Any]:
    """
    Initializes a fresh Git repository in target_dir with authentic commits and tags.
    """
    if os.path.exists(target_dir):
        # Clean existing directory safely
        shutil.rmtree(target_dir, ignore_errors=True)

    os.makedirs(target_dir, exist_ok=True)

    # 1. Initialize Git repository
    run_git(["init", "-b", "main"], cwd=target_dir)
    run_git(["config", "user.name", "TestPrioritize Demo Bot"], cwd=target_dir)
    run_git(["config", "user.email", "demo@testprioritize.ai"], cwd=target_dir)
    run_git(["config", "commit.gpgsign", "false"], cwd=target_dir)

    # ------------------------------------------------------------------------
    # Base Commit: Core Application and Full Test Suite
    # ------------------------------------------------------------------------
    write_file(target_dir, "README.md", """# Demo E-Commerce Platform
A lightweight e-commerce domain model used for testing and benchmarking
the TestPrioritize AI prioritization pipeline.
""")

    write_file(target_dir, "requirements.txt", """pytest>=7.4.0
requests==2.28.0
""")

    write_file(target_dir, "src/__init__.py", "")

    write_file(target_dir, "src/cart.py", '''"""
src/cart.py — Shopping Cart Module
"""
from typing import List, Dict, Any


def calculate_cart_total(items: List[Dict[str, Any]]) -> float:
    """Calculates total price from cart items list."""
    if not isinstance(items, list):
        raise TypeError("Items must be a list")
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

    write_file(target_dir, "src/checkout.py", '''"""
src/checkout.py — Checkout & Payment Module
"""
from typing import Dict, Any


def apply_tax(amount: float, tax_rate: float) -> float:
    """
    Calculates amount including tax, rounded strictly to 2 decimal places.
    """
    if not isinstance(amount, (int, float)) or not isinstance(tax_rate, (int, float)):
        raise TypeError("Amount and tax rate must be numeric")
    if amount < 0 or tax_rate < 0:
        raise ValueError("Amount and tax rate cannot be negative")
    # Correct intended implementation: rounds accurately
    return round(amount * (1.0 + tax_rate), 2)


def calculate_order_final(subtotal: float, tax_rate: float, shipping_fee: float) -> float:
    """Calculates final order cost including tax and shipping."""
    taxed = apply_tax(subtotal, tax_rate)
    return round(taxed + shipping_fee, 2)


def validate_shipping_address(addr: Dict[str, Any]) -> bool:
    """Validates shipping address completeness."""
    if not isinstance(addr, dict):
        return False
    required = ["street", "city", "postal_code", "country"]
    return all(bool(addr.get(k)) for k in required)
''')

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
    if quantity >= 50:
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

    write_file(target_dir, "src/user_service.py", '''"""
src/user_service.py — User Profile & Notification Service (Unrelated Module)
"""
from typing import Dict, Any


def authenticate_user(username: str, password_hash: str) -> bool:
    """Validates credentials against user directory."""
    if not username or not password_hash:
        return False
    return len(username) >= 3 and len(password_hash) == 64


def get_user_tier(loyalty_points: int) -> str:
    """Determines user reward tier."""
    if loyalty_points >= 1000:
        return "PLATINUM"
    elif loyalty_points >= 500:
        return "GOLD"
    elif loyalty_points >= 100:
        return "SILVER"
    return "STANDARD"
''')

    write_file(target_dir, "tests/__init__.py", "")

    write_file(target_dir, "tests/test_cart.py", '''"""
tests/test_cart.py
Unit tests for src/cart.py
"""
import pytest
from src.cart import calculate_cart_total, apply_coupon


def test_calculate_cart_total_empty():
    assert calculate_cart_total([]) == 0.0


def test_calculate_cart_total_single_item():
    items = [{"price": 19.99, "quantity": 1}]
    assert calculate_cart_total(items) == 19.99


def test_calculate_cart_total_multiple_quantities():
    items = [
        {"price": 10.00, "quantity": 2},
        {"price": 5.50, "quantity": 3}
    ]
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


def test_apply_coupon_save10():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_save20():
    assert apply_coupon(50.0, "SAVE20") == 40.0


def test_apply_coupon_halfprice():
    assert apply_coupon(80.0, "HALFPRICE") == 40.0


def test_apply_coupon_invalid_code():
    assert apply_coupon(100.0, "INVALID") == 100.0


def test_apply_coupon_negative_total():
    with pytest.raises(ValueError):
        apply_coupon(-10.0, "SAVE10")
''')

    write_file(target_dir, "tests/test_checkout.py", '''"""
tests/test_checkout.py
Unit tests for src/checkout.py
"""
import pytest
from src.checkout import apply_tax, calculate_order_final, validate_shipping_address


def test_apply_tax_standard():
    assert apply_tax(100.0, 0.05) == 105.0


def test_apply_tax_zero_rate():
    assert apply_tax(50.0, 0.0) == 50.0


def test_apply_tax_fractional_precision():
    """
    CRITICAL TEST: Ensures tax calculation correctly rounds fractional cents.
    Example: 10.55 * 1.08 = 11.394 -> must round to 11.39!
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


def test_validate_shipping_address_valid():
    addr = {
        "street": "123 Tech Way",
        "city": "New Delhi",
        "postal_code": "110020",
        "country": "India"
    }
    assert validate_shipping_address(addr) is True


def test_validate_shipping_address_missing_field():
    addr = {
        "street": "123 Tech Way",
        "city": "New Delhi"
    }
    assert validate_shipping_address(addr) is False
''')

    write_file(target_dir, "tests/test_pricing.py", '''"""
tests/test_pricing.py
Unit tests for src/pricing.py
"""
import pytest
from src.pricing import calculate_bulk_discount, format_currency


def test_bulk_discount_under_threshold():
    assert calculate_bulk_discount(5, 10.0) == 50.0


def test_bulk_discount_tier_10():
    # 10 items * 10.0 = 100 -> 10% off = 90.0
    assert calculate_bulk_discount(10, 10.0) == 90.0


def test_bulk_discount_tier_20():
    # 20 items * 10.0 = 200 -> 15% off = 170.0
    assert calculate_bulk_discount(20, 10.0) == 170.0


def test_bulk_discount_tier_50():
    # 50 items * 10.0 = 500 -> 25% off = 375.0
    assert calculate_bulk_discount(50, 10.0) == 375.0


def test_format_currency_usd():
    assert format_currency(1234.50) == "$1,234.50"


def test_format_currency_inr():
    assert format_currency(500.0, symbol="₹") == "₹500.00"
''')

    write_file(target_dir, "tests/test_user_service.py", '''"""
tests/test_user_service.py
Unit tests for src/user_service.py (Unrelated control tests)
"""
import pytest
from src.user_service import authenticate_user, get_user_tier


def test_authenticate_user_valid():
    dummy_hash = "a" * 64
    assert authenticate_user("admin", dummy_hash) is True


def test_authenticate_user_empty():
    assert authenticate_user("", "") is False


def test_get_user_tier_standard():
    assert get_user_tier(50) == "STANDARD"


def test_get_user_tier_silver():
    assert get_user_tier(150) == "SILVER"


def test_get_user_tier_gold():
    assert get_user_tier(600) == "GOLD"


def test_get_user_tier_platinum():
    assert get_user_tier(1200) == "PLATINUM"
''')

    # Commit baseline
    run_git(["add", "."], cwd=target_dir)
    run_git(["commit", "-m", "Initial commit: Core platform and comprehensive test suite"], cwd=target_dir)
    base_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "base"], cwd=target_dir)

    # ------------------------------------------------------------------------
    # Scenario 1: Cart Calculation Enhancement (Healthy PR)
    # ------------------------------------------------------------------------
    run_git(["checkout", "-b", "feature/cart-enhancement"], cwd=target_dir)
    cart_enhancement_code = '''"""
src/cart.py — Shopping Cart Module (Enhanced with Max Quantity Validation)
"""
from typing import List, Dict, Any

MAX_CART_ITEMS = 50


def calculate_cart_total(items: List[Dict[str, Any]]) -> float:
    """Calculates total price from cart items list with item limit checks."""
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
'''
    write_file(target_dir, "src/cart.py", cart_enhancement_code)
    run_git(["add", "src/cart.py"], cwd=target_dir)
    run_git(["commit", "-m", "feat(cart): enforce maximum item limit of 50 items"], cwd=target_dir)
    cart_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "cart-enhancement"], cwd=target_dir)

    # ------------------------------------------------------------------------
    # Scenario 2: Authentic Failing Regression in Checkout (Intentional Bug)
    # ------------------------------------------------------------------------
    # Checkout clean base commit
    run_git(["checkout", "main"], cwd=target_dir)
    run_git(["checkout", "-b", "regression/checkout-rounding-bug"], cwd=target_dir)

    # Regression: Developer replaced accurate round(amount * (1 + tax), 2)
    # with integer truncation: int(amount * (1 + tax_rate))
    # This causes test_apply_tax_fractional_precision to fail!
    checkout_regression_code = '''"""
src/checkout.py — Checkout & Payment Module (WITH INTENTIONAL REGRESSION)
"""
from typing import Dict, Any


def apply_tax(amount: float, tax_rate: float) -> float:
    """
    Calculates amount including tax.
    REGRESSION: Integer truncation causes precision loss on fractional cents!
    """
    if not isinstance(amount, (int, float)) or not isinstance(tax_rate, (int, float)):
        raise TypeError("Amount and tax rate must be numeric")
    if amount < 0 or tax_rate < 0:
        raise ValueError("Amount and tax rate cannot be negative")
    # INTRODUCED BUG: Truncates decimal cents! (e.g. 11.39 becomes 11.0)
    return float(int(amount * (1.0 + tax_rate)))


def calculate_order_final(subtotal: float, tax_rate: float, shipping_fee: float) -> float:
    """Calculates final order cost including tax and shipping."""
    taxed = apply_tax(subtotal, tax_rate)
    return round(taxed + shipping_fee, 2)


def validate_shipping_address(addr: Dict[str, Any]) -> bool:
    """Validates shipping address completeness."""
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

    # ------------------------------------------------------------------------
    # Scenario 3: Multi-Module Overhaul (Cart + Pricing)
    # ------------------------------------------------------------------------
    run_git(["checkout", "main"], cwd=target_dir)
    run_git(["checkout", "-b", "feature/bulk-pricing-update"], cwd=target_dir)

    pricing_update_code = '''"""
src/pricing.py — Pricing Rules & Bulk Discount Engine
"""
from typing import Dict, Any


def calculate_bulk_discount(quantity: int, unit_price: float) -> float:
    """Calculates volume pricing discounts with VIP tier at 100 items."""
    if not isinstance(quantity, int) or not isinstance(unit_price, (int, float)):
        raise TypeError("Quantity and unit price must be numbers")
    if quantity < 0 or unit_price < 0:
        raise ValueError("Quantity and unit price must be positive")
    
    total = quantity * unit_price
    if quantity >= 100:
        return round(total * 0.70, 2)  # 30% off for 100+
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
'''
    write_file(target_dir, "src/pricing.py", pricing_update_code)
    write_file(target_dir, "src/cart.py", cart_enhancement_code)
    run_git(["add", "src/pricing.py", "src/cart.py"], cwd=target_dir)
    run_git(["commit", "-m", "feat(pricing): add VIP bulk tier and cart limit checks"], cwd=target_dir)
    bulk_pricing_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "bulk-pricing"], cwd=target_dir)

    # ------------------------------------------------------------------------
    # Scenario 4: Dependency Manifest Upgrade (TinyFish Trigger)
    # ------------------------------------------------------------------------
    run_git(["checkout", "main"], cwd=target_dir)
    run_git(["checkout", "-b", "chore/dependency-upgrade"], cwd=target_dir)

    # Upgrade requests from 2.28.0 to 3.0.0
    write_file(target_dir, "requirements.txt", """pytest>=7.4.0
requests==3.0.0
""")
    run_git(["add", "requirements.txt"], cwd=target_dir)
    run_git(["commit", "-m", "chore(deps): upgrade requests to 3.0.0"], cwd=target_dir)
    dep_commit = run_git(["rev-parse", "HEAD"], cwd=target_dir)
    run_git(["tag", "dep-upgrade"], cwd=target_dir)

    # Reset working tree back to main
    run_git(["checkout", "main"], cwd=target_dir)

    # Build scenario catalogue
    scenarios = [
        {
            "id": "cart_enhancement",
            "title": "Scenario 1: Cart Calculation Enhancement (Healthy PR)",
            "description": "Adds cart item limits to src/cart.py. Demonstrates clean test prioritization where tests/test_cart.py ranks #1 with 100% pass rate.",
            "base_ref": "base",
            "target_ref": "cart-enhancement",
            "base_commit": base_commit,
            "target_commit": cart_commit,
            "is_regression": False,
            "expected_changed_files": ["src/cart.py"],
            "expected_top_test": "tests/test_cart.py",
            "expected_pass_rate": 1.0,
            "notes": "Healthy code change; all tests pass."
        },
        {
            "id": "checkout_regression",
            "title": "Scenario 2: Currency Rounding Regression (Authentic Failing Demo)",
            "description": "An intentional regression in src/checkout.py truncates fractional cents. Prioritizes tests/test_checkout.py to rank #1, catching the failure immediately via fail-fast.",
            "base_ref": "base",
            "target_ref": "checkout-regression",
            "base_commit": base_commit,
            "target_commit": checkout_bug_commit,
            "is_regression": True,
            "expected_changed_files": ["src/checkout.py"],
            "expected_top_test": "tests/test_checkout.py",
            "detecting_test": "tests/test_checkout.py::test_apply_tax_fractional_precision",
            "regression_details": {
                "intended_behavior": "apply_tax(10.55, 0.08) computes 10.55 * 1.08 = 11.394 and rounds to 11.39",
                "introduced_regression": "apply_tax uses float(int(amount * (1.0 + tax_rate))) which truncates 11.394 to 11.0",
                "detecting_test": "tests/test_checkout.py::test_apply_tax_fractional_precision",
                "expected_outcome": "11.39",
                "observed_outcome": "11.0"
            },
            "notes": "Authentic regression demonstration; test fails legitimately without fake logs."
        },
        {
            "id": "multi_module_pricing",
            "title": "Scenario 3: Multi-Module Overhaul (Cart + Pricing)",
            "description": "Updates both src/cart.py and src/pricing.py. Demonstrates multi-source corroboration ranking where tests touching both modules receive elevated scores.",
            "base_ref": "base",
            "target_ref": "bulk-pricing",
            "base_commit": base_commit,
            "target_commit": bulk_pricing_commit,
            "is_regression": False,
            "expected_changed_files": ["src/cart.py", "src/pricing.py"],
            "expected_top_test": "tests/test_cart.py",
            "expected_pass_rate": 1.0,
            "notes": "Tests multi-file change detection and score distribution."
        },
        {
            "id": "dependency_upgrade",
            "title": "Scenario 4: Dependency Upgrade (TinyFish Manifest Change)",
            "description": "Upgrades requests from 2.28.0 to 3.0.0 in requirements.txt. Activates TinyFish dependency intelligence to query breaking changes and assign dependency risk bonuses.",
            "base_ref": "base",
            "target_ref": "dep-upgrade",
            "base_commit": base_commit,
            "target_commit": dep_commit,
            "is_regression": False,
            "expected_changed_files": ["requirements.txt"],
            "expected_top_test": None,
            "expected_pass_rate": 1.0,
            "notes": "Triggers manifest version delta computation and TinyFish query generation."
        }
    ]

    manifest_path = os.path.join(target_dir, "scenarios.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2)

    return {
        "repo_path": target_dir,
        "base_commit": base_commit,
        "scenarios": scenarios
    }

    if __name__ == "__main__":
        print(f"Initializing demo repository in: {DEMO_DIR}")
        info = init_demo_repository()
        print("Demo repository initialized successfully!")
        print(f"Base commit: {info['base_commit'][:7]}")
        print(f"Created {len(info['scenarios'])} reproducible scenarios.")

