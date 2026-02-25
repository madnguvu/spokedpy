"""
Demo 5 — Registry Stress Test
===============================
A larger file with many small functions to populate the Engine Matrix.
Import this to see row 'a' (Python) fill up with 8 slots — the
maximum per engine row.

In REGISTRY mode:
  - "Run All" commits all 8 functions to slots a1–a8
  - The entire Python row lights up during execution
  - You'll see a cascade of green flashes as each slot succeeds
  - The stats line shows "8 committed · 0 pending · 8 total"
"""

import time
import hashlib
import json


def slot_alpha() -> str:
    """Slot a1 — Simple string work."""
    result = "ALPHA".lower().replace("a", "@")
    print(f"[a1] Alpha: {result}")
    return result


def slot_bravo() -> dict:
    """Slot a2 — Dictionary construction."""
    data = {chr(65 + i): i ** 2 for i in range(5)}
    print(f"[a2] Bravo: {data}")
    return data


def slot_charlie() -> list:
    """Slot a3 — List comprehension with filter."""
    primes = [n for n in range(2, 30) if all(n % d != 0 for d in range(2, n))]
    print(f"[a3] Charlie: primes → {primes}")
    return primes


def slot_delta() -> float:
    """Slot a4 — Timing measurement."""
    start = time.perf_counter()
    total = sum(i * i for i in range(10_000))
    elapsed = time.perf_counter() - start
    print(f"[a4] Delta: sum of squares = {total}, took {elapsed*1000:.2f}ms")
    return elapsed


def slot_echo() -> str:
    """Slot a5 — Hashing."""
    message = "SpokedPy Engine Matrix"
    digest = hashlib.sha256(message.encode()).hexdigest()[:16]
    print(f"[a5] Echo: SHA-256('{message}') = {digest}…")
    return digest


def slot_foxtrot() -> list:
    """Slot a6 — Nested data structure."""
    records = [
        {"id": i, "name": f"node_{i}", "active": i % 2 == 0}
        for i in range(1, 6)
    ]
    print(f"[a6] Foxtrot: {len(records)} records")
    for r in records:
        status = "●" if r["active"] else "○"
        print(f"     {status} {r['name']}")
    return records


def slot_golf() -> str:
    """Slot a7 — JSON serialization round-trip."""
    obj = {"matrix": [[1, 0], [0, 1]], "label": "identity"}
    serialized = json.dumps(obj, separators=(",", ":"))
    restored = json.loads(serialized)
    match = obj == restored
    print(f"[a7] Golf: JSON round-trip {'✅ OK' if match else '❌ FAIL'}")
    print(f"     Compact: {serialized}")
    return serialized


def slot_hotel() -> int:
    """Slot a8 — The last slot: a grand summary."""
    values = [len(slot_alpha.__name__),
              len(slot_bravo.__name__),
              len(slot_charlie.__name__),
              len(slot_delta.__name__),
              len(slot_echo.__name__),
              len(slot_foxtrot.__name__),
              len(slot_golf.__name__)]
    total = sum(values)
    print(f"[a8] Hotel: function-name-length checksum = {total}")
    print(f"     All 8 slots executed. Engine row 'a' complete! 🏁")
    return total
