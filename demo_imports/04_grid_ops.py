"""
Demo 4 — Matrix & Grid Operations
===================================
Functions that work with 2D grids — a thematic match for the
Engine Matrix display. Run these and watch the matrix grid
light up while they compute grids of their own!

Best viewed in REGISTRY mode so you can see the matrix
populate with committed nodes before execution.
"""

import random


def create_grid(rows: int = 4, cols: int = 6) -> list:
    """Create a 2D grid filled with random values 0–9."""
    random.seed(42)  # Deterministic for demo
    grid = [[random.randint(0, 9) for _ in range(cols)] for _ in range(rows)]
    print(f"🔲 Created {rows}×{cols} grid:")
    for row in grid:
        print("   " + " ".join(f"{v:2d}" for v in row))
    return grid


def transpose(grid: list) -> list:
    """Transpose a 2D grid (swap rows ↔ columns)."""
    rows = len(grid)
    cols = len(grid[0]) if grid else 0
    result = [[grid[r][c] for r in range(rows)] for c in range(cols)]
    print(f"🔄 Transposed {rows}×{cols} → {cols}×{rows}:")
    for row in result:
        print("   " + " ".join(f"{v:2d}" for v in row))
    return result


def row_sums(grid: list) -> list:
    """Compute the sum of each row."""
    sums = [sum(row) for row in grid]
    print(f"➕ Row sums: {sums}")
    print(f"   Total: {sum(sums)}")
    return sums


def find_max_cell(grid: list) -> dict:
    """Find the position and value of the maximum cell."""
    max_val = -1
    max_pos = (0, 0)
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            if val > max_val:
                max_val = val
                max_pos = (r, c)
    result = {"row": max_pos[0], "col": max_pos[1], "value": max_val}
    print(f"🏆 Max cell: value={max_val} at row={max_pos[0]}, col={max_pos[1]}")
    return result


def flatten(grid: list) -> list:
    """Flatten a 2D grid into a sorted 1D list."""
    flat = sorted([val for row in grid for val in row])
    print(f"📏 Flattened & sorted ({len(flat)} values): {flat}")
    return flat
