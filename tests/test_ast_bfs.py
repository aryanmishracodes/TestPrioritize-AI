"""
tests/test_ast_bfs.py
Unit tests for isolated Breadth-First Search (BFS) AST traversal:
1. Validates strict level-by-level (BFS) traversal order.
2. Validates complete AST node coverage compared to exhaustive traversal.
3. Validates duplicate prevention (every node visited exactly once).
4. Validates edge cases: non-AST input, leaf nodes, synthetic shared children.
5. Validates real-world source files from the repository.
"""

import ast
import os
import pytest
from ast_bfs import bfs_walk, collect_nodes_bfs
from test_mapper import bfs_walk as mapper_bfs_walk


def test_bfs_traversal_order_level_by_level():
    """
    Verifies that bfs_walk visits nodes in strict level-order (depth 0, depth 1, depth 2, etc.).
    """
    code = """
def calculate(a, b):
    total = a + b
    return total
"""
    tree = ast.parse(code)
    nodes = list(bfs_walk(tree))

    assert len(nodes) > 0
    # Level 0: Module
    assert isinstance(nodes[0], ast.Module)

    # Compute expected levels using BFS on iter_child_nodes
    expected_depths = {id(tree): 0}
    queue = [tree]
    while queue:
        curr = queue.pop(0)
        curr_depth = expected_depths[id(curr)]
        for child in ast.iter_child_nodes(curr):
            if id(child) not in expected_depths:
                expected_depths[id(child)] = curr_depth + 1
                queue.append(child)

    actual_depths = [expected_depths[id(n)] for n in nodes]
    # In BFS traversal, node depths must be monotonically non-decreasing
    for i in range(len(actual_depths) - 1):
        assert actual_depths[i] <= actual_depths[i + 1], (
            f"BFS depth violation at index {i}: depth {actual_depths[i]} followed by {actual_depths[i + 1]}"
        )


def test_complete_ast_node_coverage():
    """
    Verifies that bfs_walk visits every single node in the AST with 100% coverage
    compared to Python's standard ast.walk.
    """
    code = """
import os
from math import sqrt

class Processor:
    def __init__(self, value: int):
        self.value = value

    def compute(self, factor: float) -> float:
        if factor > 0:
            return sqrt(self.value) * factor
        return 0.0
"""
    tree = ast.parse(code)
    bfs_nodes = list(bfs_walk(tree))
    std_walk_nodes = list(ast.walk(tree))

    # Every unique node in the AST must be visited exactly once
    unique_std_ids = set(id(n) for n in std_walk_nodes)
    assert len(bfs_nodes) == len(unique_std_ids)
    assert set(id(n) for n in bfs_nodes) == unique_std_ids


def test_duplicate_prevention_each_node_visited_exactly_once():
    """
    Verifies that no node is visited more than once.
    """
    code = """
x = 10
y = 20
z = x + y
print(z)
"""
    tree = ast.parse(code)
    nodes = list(bfs_walk(tree))
    visited_ids = [id(n) for n in nodes]

    # Length of list must equal length of unique set
    assert len(visited_ids) == len(set(visited_ids)), "Duplicate node visits detected!"


def test_duplicate_prevention_with_shared_or_cyclic_child_nodes():
    """
    Verifies that if an AST artificially shares child node references,
    bfs_walk visits each node object exactly once without looping or duplicating.
    """
    shared_const = ast.Constant(value=42)
    expr1 = ast.Expr(value=shared_const)
    expr2 = ast.Expr(value=shared_const)
    root = ast.Module(body=[expr1, expr2], type_ignores=[])

    nodes = list(bfs_walk(root))
    const_nodes = [n for n in nodes if n is shared_const]

    # Even though shared_const is referenced by both expr1 and expr2,
    # it must be yielded exactly once.
    assert len(const_nodes) == 1
    assert len(nodes) == len(set(id(n) for n in nodes))


def test_edge_cases_non_ast_and_single_nodes():
    """
    Verifies graceful handling of non-AST objects, None, and isolated leaf nodes.
    """
    assert list(bfs_walk(None)) == []
    assert list(bfs_walk("not an ast")) == []
    assert list(bfs_walk(123)) == []

    single = ast.Pass()
    nodes = list(bfs_walk(single))
    assert len(nodes) == 1
    assert nodes[0] is single


def test_collect_nodes_bfs_helper():
    """
    Verifies collect_nodes_bfs returns a complete list matching bfs_walk.
    """
    tree = ast.parse("a = 1")
    nodes_from_walk = list(bfs_walk(tree))
    nodes_from_helper = collect_nodes_bfs(tree)

    assert nodes_from_walk == nodes_from_helper
    assert len(nodes_from_helper) > 0


def test_test_mapper_exports_bfs_walk():
    """
    Verifies test_mapper exports bfs_walk identically.
    """
    tree = ast.parse("import cart")
    nodes1 = list(bfs_walk(tree))
    nodes2 = list(mapper_bfs_walk(tree))

    assert [id(n) for n in nodes1] == [id(n) for n in nodes2]


def test_real_workspace_source_files():
    """
    Verifies bfs_walk on real application source files in src/.
    """
    for file_name in ["src/cart.py", "src/checkout.py"]:
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            bfs_nodes = list(bfs_walk(tree))
            std_nodes = list(ast.walk(tree))
            unique_std_ids = set(id(n) for n in std_nodes)
            assert len(bfs_nodes) == len(unique_std_ids)
            assert set(id(n) for n in bfs_nodes) == unique_std_ids
