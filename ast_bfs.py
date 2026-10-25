"""
ast_bfs.py
Part of TestPrioritize AI.

Isolated Breadth-First Search (BFS) AST traversal helper.
Traverses a parsed Python Abstract Syntax Tree level-by-level using
collections.deque and ast.iter_child_nodes(node), ensuring that every
node in the tree is visited exactly once.
"""

import ast
from collections import deque
from typing import Iterator, List, Optional, Set


def bfs_walk(node: ast.AST) -> Iterator[ast.AST]:
    """
    Yields all nodes in the parsed AST in breadth-first (level-order) sequence.
    
    Starting at the root node, yields the root, then all depth-1 children,
    then all depth-2 grandchildren, and so forth.
    
    Guarantees:
    - Uses collections.deque for O(1) FIFO queue operations.
    - Uses ast.iter_child_nodes(node) to discover direct syntax children.
    - Tracks visited node IDs to guarantee every node is visited exactly once.
    - Safe against malformed inputs (non-AST inputs return immediately).
    
    Args:
        node: The root ast.AST node to traverse.
        
    Yields:
        ast.AST nodes in level-order.
    """
    if not isinstance(node, ast.AST):
        return

    queue: deque[ast.AST] = deque([node])
    visited: Set[int] = {id(node)}

    while queue:
        current = queue.popleft()
        yield current

        for child in ast.iter_child_nodes(current):
            child_id = id(child)
            if child_id not in visited:
                visited.add(child_id)
                queue.append(child)


def collect_nodes_bfs(node: ast.AST) -> List[ast.AST]:
    """
    Convenience helper that returns a list of all AST nodes in BFS order.
    """
    return list(bfs_walk(node))
