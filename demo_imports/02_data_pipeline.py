"""
Demo 2 — Data Pipeline
=======================
Multiple functions that pass data through a pipeline.
Each function is a separate node in the ledger.

Try in LEDGER mode:
  - "Run All" — runs each node top-to-bottom in a shared namespace
  - Variables panel shows the growing state

Then switch to REGISTRY mode:
  - "Run All" — commits every node to the Engine Matrix first
  - Watch multiple slots on row 'a' (Python) light up
  - Each slot flashes green (success) or red (error) after execution
"""

import math


def generate_data(size: int = 10) -> list:
    """Generate a list of sample measurements."""
    data = [round(math.sin(i * 0.5) * 100 + 150, 2) for i in range(size)]
    print(f"📊 Generated {len(data)} data points")
    print(f"   Range: {min(data):.1f} – {max(data):.1f}")
    return data


def filter_outliers(data: list, threshold: float = 100.0) -> list:
    """Remove values below threshold."""
    mean = sum(data) / len(data)
    filtered = [x for x in data if abs(x - mean) < threshold]
    removed = len(data) - len(filtered)
    print(f"🔍 Filtered: kept {len(filtered)}, removed {removed} outlier(s)")
    return filtered


def compute_stats(data: list) -> dict:
    """Compute basic statistics on the data."""
    n = len(data)
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / n
    std_dev = math.sqrt(variance)

    stats = {
        "count": n,
        "mean": round(mean, 2),
        "std_dev": round(std_dev, 2),
        "min": min(data),
        "max": max(data),
    }
    print(f"📈 Stats: mean={stats['mean']}, σ={stats['std_dev']}, n={stats['count']}")
    return stats


def summarize(stats: dict) -> str:
    """Produce a human-readable summary string."""
    summary = (
        f"Dataset of {stats['count']} points: "
        f"μ={stats['mean']}, σ={stats['std_dev']}, "
        f"range=[{stats['min']}, {stats['max']}]"
    )
    print(f"📋 {summary}")
    return summary
