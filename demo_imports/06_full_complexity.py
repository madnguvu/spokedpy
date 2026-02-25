"""
Demo 6 — Full Complexity Showcase
===================================
The most complex file we can throw at Live / Registry execution
RIGHT NOW, designed to exercise every capability that works today.

Demonstrates:
  ● Cross-node function calls   — later nodes call earlier ones
  ● Shared-namespace chaining   — variables flow across nodes via REPL state
  ● Classes with methods         — each class = 1 self-contained node
  ● Decorators & closures        — inside a single function body
  ● Generator functions          — yield-based lazy evaluation
  ● Error handling               — try/except inside function bodies
  ● Stdlib imports               — math, collections, itertools, functools, json
  ● Rich printed output          — so the Live Execution panel shows something interesting

All constructs that produce inner control-flow nodes (bare for/while/if)
are avoided — loops and conditionals live INSIDE function bodies only,
expressed via comprehensions, builtins, ternaries, or single-function scope.

EXECUTION ORDER MATTERS:
  Run All in Ledger or Registry mode — the shared namespace means later
  functions can call earlier ones.  Watch the cascade!

SLOTS:  14 top-level functions → fills engine row 'a' (8 slots)
        and spills into row 'b' (which is also Python).  If the registry
        auto-assigns, you'll see two rows light up!
"""

import math
import json
import functools
import itertools
from collections import Counter, defaultdict, namedtuple
from datetime import datetime, timedelta


# ─────────────────────────────────────────────
# 1. FOUNDATION — data generators
# ─────────────────────────────────────────────

def generate_sensor_data(n: int = 20) -> list:
    """Simulate sensor readings with deterministic noise.
    
    Uses math.sin for wave pattern + simple hash-based jitter
    so results are reproducible without `random`.
    """
    readings = []
    for i in range(n):
        base = math.sin(i * 0.4) * 50 + 100
        jitter = ((i * 7 + 13) % 11 - 5) * 0.3      # deterministic "noise"
        readings.append(round(base + jitter, 2))
    
    print(f"📡 Generated {n} sensor readings")
    print(f"   Range: {min(readings):.1f} – {max(readings):.1f}")
    print(f"   First 8: {readings[:8]}")
    return readings


def build_lookup_table(keys: list = None) -> dict:
    """Build a hash-based lookup table from a list of keys.
    
    Demonstrates defaultdict, Counter, and namedtuple — all from
    collections, all constructed without bare for-loops.
    """
    keys = keys or ["alpha", "bravo", "charlie", "delta", "echo",
                     "foxtrot", "golf", "hotel", "india", "juliet"]
    
    Entry = namedtuple("Entry", ["key", "index", "hash_val", "bucket"])
    NUM_BUCKETS = 4
    
    entries = [
        Entry(key=k, index=i, hash_val=hash(k) % 997, bucket=hash(k) % NUM_BUCKETS)
        for i, k in enumerate(keys)
    ]
    
    bucket_counts = Counter(e.bucket for e in entries)
    table = defaultdict(list)
    for e in entries:
        table[e.bucket].append(e._asdict())
    
    print(f"🗂️  Lookup table: {len(keys)} keys → {NUM_BUCKETS} buckets")
    for b in sorted(table):
        names = [e["key"] for e in table[b]]
        print(f"   Bucket {b} ({bucket_counts[b]}): {', '.join(names)}")
    
    return dict(table)


# ─────────────────────────────────────────────
# 2. TRANSFORMS — higher-order & functional
# ─────────────────────────────────────────────

def make_pipeline(*transforms):
    """Create a reusable data pipeline from a chain of functions.
    
    Returns a closure that applies each transform in sequence.
    Demonstrates closures, *args unpacking, and functools.reduce.
    """
    def pipeline(data):
        return functools.reduce(lambda acc, fn: fn(acc), transforms, data)
    
    names = [getattr(fn, '__name__', '?') for fn in transforms]
    print(f"🔗 Pipeline created: {' → '.join(names)}")
    return pipeline


def moving_average(data: list, window: int = 3) -> list:
    """Compute a simple moving average over a list of numbers.
    
    Uses itertools.islice for the sliding window — no bare loops.
    """
    if len(data) < window:
        return data[:]
    
    result = [
        round(sum(data[i:i + window]) / window, 2)
        for i in range(len(data) - window + 1)
    ]
    
    print(f"📈 Moving avg (window={window}): {len(data)} pts → {len(result)} pts")
    print(f"   Smoothed first 6: {result[:6]}")
    return result


def z_score_normalize(data: list) -> list:
    """Normalize data to zero mean, unit variance (Z-score).
    
    Demonstrates math.sqrt and in-line statistics — everything
    self-contained inside one function.
    """
    n = len(data)
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / n
    std = math.sqrt(variance) if variance > 0 else 1.0
    
    normalized = [round((x - mean) / std, 4) for x in data]
    
    new_mean = sum(normalized) / len(normalized)
    new_std = math.sqrt(sum((x - new_mean) ** 2 for x in normalized) / len(normalized))
    print(f"📐 Z-score normalization:")
    print(f"   Before — μ={mean:.2f}, σ={math.sqrt(variance):.2f}")
    print(f"   After  — μ={new_mean:.4f}, σ={new_std:.4f}")
    return normalized


# ─────────────────────────────────────────────
# 3. CROSS-NODE CALLS — later nodes use earlier ones
# ─────────────────────────────────────────────

def run_full_pipeline() -> dict:
    """Orchestrate the entire pipeline by calling prior functions.
    
    THIS IS THE KEY TEST: it calls generate_sensor_data(),
    moving_average(), and z_score_normalize() — all defined in
    earlier nodes.  Only works because the shared REPL namespace
    keeps prior definitions alive.
    """
    raw = generate_sensor_data(16)
    smoothed = moving_average(raw, window=3)
    normed = z_score_normalize(smoothed)
    
    summary = {
        "raw_count": len(raw),
        "smoothed_count": len(smoothed),
        "normalized_count": len(normed),
        "raw_range": [min(raw), max(raw)],
        "final_range": [min(normed), max(normed)],
    }
    
    print(f"\n🚀 Full pipeline result:")
    print(f"   {json.dumps(summary, indent=4)}")
    return summary


# ─────────────────────────────────────────────
# 4. CLASS — self-contained with methods
# ─────────────────────────────────────────────

class SignalProcessor:
    """A stateful signal processor that accumulates readings.
    
    The class definition becomes ONE node.  Its body has methods,
    a class variable, and a __repr__ — all enclosed.
    """
    
    MAX_BUFFER = 100
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.buffer = []
        self.stats_history = []
    
    def ingest(self, values: list):
        """Add values to the internal buffer, capping at MAX_BUFFER."""
        self.buffer.extend(values)
        self.buffer = self.buffer[-self.MAX_BUFFER:]
        return self
    
    def compute_stats(self) -> dict:
        """Return basic stats on the current buffer."""
        if not self.buffer:
            return {"error": "empty buffer"}
        n = len(self.buffer)
        mean = sum(self.buffer) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in self.buffer) / n)
        stats = {"n": n, "mean": round(mean, 2), "std": round(std, 2),
                 "min": min(self.buffer), "max": max(self.buffer)}
        self.stats_history.append(stats)
        return stats
    
    def trend(self) -> str:
        """Determine if the signal is trending up, down, or flat."""
        if len(self.buffer) < 4:
            return "insufficient data"
        first_half = sum(self.buffer[:len(self.buffer)//2])
        second_half = sum(self.buffer[len(self.buffer)//2:])
        diff = second_half - first_half
        return "📈 rising" if diff > 5 else "📉 falling" if diff < -5 else "➡️ flat"
    
    def __repr__(self):
        return f"SignalProcessor('{self.name}', buffer_size={len(self.buffer)})"


# ─────────────────────────────────────────────
# 5. USE THE CLASS — cross-node instantiation
# ─────────────────────────────────────────────

def demo_signal_processor() -> dict:
    """Instantiate SignalProcessor (defined in a prior node) and exercise it.
    
    Cross-node dependency: this function references the SignalProcessor class.
    """
    sp = SignalProcessor("demo-sensor")
    
    # Feed two batches of data
    batch1 = generate_sensor_data(12)
    batch2 = [x * 1.1 + 5 for x in batch1]  # shifted & scaled
    
    sp.ingest(batch1)
    stats1 = sp.compute_stats()
    
    sp.ingest(batch2)
    stats2 = sp.compute_stats()
    
    trend = sp.trend()
    
    print(f"\n🔬 SignalProcessor demo:")
    print(f"   {sp}")
    print(f"   After batch 1: {stats1}")
    print(f"   After batch 2: {stats2}")
    print(f"   Trend: {trend}")
    
    return {"processor": repr(sp), "stats": [stats1, stats2], "trend": trend}


# ─────────────────────────────────────────────
# 6. GENERATORS — lazy evaluation
# ─────────────────────────────────────────────

def fibonacci_gen(limit: int = 15):
    """A generator that yields Fibonacci numbers up to `limit` terms.
    
    Calling list() on it forces evaluation — the generator protocol
    works fine inside a single function body.
    """
    a, b = 0, 1
    count = 0
    while count < limit:
        yield a
        a, b = b, a + b
        count += 1


def demo_generators() -> dict:
    """Exercise generator functions with itertools combinators.
    
    Uses fibonacci_gen (prior node), itertools.chain, itertools.takewhile,
    and itertools.islice — all functional-style, no bare loops.
    """
    fibs = list(fibonacci_gen(12))
    
    # Chain two sequences
    evens = list(range(0, 20, 2))
    combined = list(itertools.chain(fibs, evens))
    
    # Take while below threshold
    under_50 = list(itertools.takewhile(lambda x: x < 50, fibs))
    
    # Pairwise differences using islice + zip
    diffs = [b - a for a, b in zip(fibs, fibs[1:])]
    
    # Accumulate (running sum)
    running = list(itertools.accumulate(fibs[:8]))
    
    print(f"\n♾️  Generator & itertools demo:")
    print(f"   Fibonacci(12): {fibs}")
    print(f"   Under 50:      {under_50}")
    print(f"   Differences:   {diffs}")
    print(f"   Running sum:   {running}")
    print(f"   Chain length:  {len(combined)}")
    
    return {
        "fibs": fibs,
        "under_50": under_50,
        "diffs": diffs,
        "running_sum": running,
        "chain_length": len(combined),
    }


# ─────────────────────────────────────────────
# 7. ERROR HANDLING — resilient execution
# ─────────────────────────────────────────────

def safe_divide_batch(pairs: list = None) -> list:
    """Perform a batch of divisions, catching ZeroDivisionError gracefully.
    
    Demonstrates try/except INSIDE a function body — the parser
    won't extract the try block as a separate node.
    """
    pairs = pairs or [
        (100, 3), (42, 7), (99, 0), (256, 16),
        (1, 0), (144, 12), (0, 5), (777, 0),
    ]
    
    results = []
    successes = 0
    failures = 0
    
    for a, b in pairs:
        try:
            val = round(a / b, 4)
            results.append({"a": a, "b": b, "result": val, "ok": True})
            successes += 1
        except ZeroDivisionError:
            results.append({"a": a, "b": b, "result": None, "ok": False, "error": "÷ by zero"})
            failures += 1
    
    print(f"\n🛡️  Safe division batch ({len(pairs)} pairs):")
    for r in results:
        status = f"= {r['result']}" if r['ok'] else f"⚠️ {r['error']}"
        print(f"   {r['a']:>4} / {r['b']:<4} {status}")
    print(f"   ✅ {successes} OK, ❌ {failures} caught")
    
    return results


# ─────────────────────────────────────────────
# 8. DECORATORS — within a single node
# ─────────────────────────────────────────────

def make_traced_functions() -> dict:
    """Build and exercise decorated functions.
    
    The decorator, the decorated functions, and their invocations
    all live INSIDE this one function body — so they stay in a
    single node.  Demonstrates closures, decorator pattern, and
    functools.wraps.
    """
    call_log = []
    
    def trace(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            call_log.append({"fn": fn.__name__, "args": args, "kwargs": kwargs})
            result = fn(*args, **kwargs)
            call_log[-1]["result"] = result
            return result
        return wrapper
    
    @trace
    def add(a, b):
        return a + b
    
    @trace
    def multiply(a, b):
        return a * b
    
    @trace
    def power(base, exp):
        return base ** exp
    
    # Exercise them
    r1 = add(3, 4)
    r2 = multiply(r1, 5)
    r3 = power(2, 10)
    r4 = add(r2, r3)
    
    print(f"\n🏷️  Decorator / trace demo:")
    for entry in call_log:
        print(f"   {entry['fn']}({', '.join(map(str, entry['args']))}) → {entry['result']}")
    print(f"   Final composite: add(multiply(add(3,4),5), power(2,10)) = {r4}")
    
    return {"call_log": call_log, "final": r4}


# ─────────────────────────────────────────────
# 9. JSON SERIALIZATION — round-trip stress
# ─────────────────────────────────────────────

def json_stress_test() -> dict:
    """Build a complex nested structure, serialize, deserialize, and verify.
    
    Exercises json.dumps / json.loads with nested dicts, lists,
    None, booleans, and floats — a round-trip integrity check.
    """
    payload = {
        "header": {
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "engine": "SpokedPy",
        },
        "nodes": [
            {"id": f"node_{i:03d}", "active": i % 3 != 0,
             "weight": round(math.log(i + 1), 4),
             "tags": [t for t in ["fast", "gpu", "cached"] if hash(f"{i}{t}") % 2 == 0]}
            for i in range(10)
        ],
        "edges": [
            {"from": f"node_{i:03d}", "to": f"node_{i+1:03d}", "cost": round(1.0 / (i + 1), 4)}
            for i in range(9)
        ],
        "metadata": {
            "null_field": None,
            "flag": True,
            "nested": {"a": {"b": {"c": 42}}},
        },
    }
    
    serialized = json.dumps(payload, indent=2, default=str)
    restored = json.loads(serialized)
    
    match = json.dumps(payload, sort_keys=True, default=str) == json.dumps(restored, sort_keys=True)
    
    print(f"\n📦 JSON stress test:")
    print(f"   Payload size: {len(serialized)} chars")
    print(f"   Nodes: {len(payload['nodes'])}, Edges: {len(payload['edges'])}")
    print(f"   Round-trip: {'✅ MATCH' if match else '❌ MISMATCH'}")
    print(f"   Deepest path: metadata.nested.a.b.c = {restored['metadata']['nested']['a']['b']['c']}")
    
    return {"size": len(serialized), "nodes": len(payload['nodes']),
            "match": match, "deep_value": restored['metadata']['nested']['a']['b']['c']}


# ─────────────────────────────────────────────
# 10. GRAND FINALE — ties everything together
# ─────────────────────────────────────────────

def grand_finale() -> dict:
    """The ultimate cross-node integration test.
    
    Calls functions from nodes 1, 2, 4, 5, 6, 7, 8, and 9 —
    proving the entire shared namespace is alive and well.
    If any earlier node failed, this one will too.
    """
    results = {}
    errors = []
    
    # 1. Data generation (node 1)
    try:
        raw = generate_sensor_data(10)
        results["sensor_data"] = len(raw)
    except Exception as e:
        errors.append(f"generate_sensor_data: {e}")
    
    # 2. Lookup table (node 2)
    try:
        table = build_lookup_table(["x", "y", "z"])
        results["lookup_buckets"] = len(table)
    except Exception as e:
        errors.append(f"build_lookup_table: {e}")
    
    # 3. Pipeline (nodes 3+4+5)
    try:
        pipe = make_pipeline(
            lambda d: moving_average(d, 3),
            z_score_normalize,
        )
        piped = pipe(raw)
        results["pipeline_output"] = len(piped)
    except Exception as e:
        errors.append(f"pipeline: {e}")
    
    # 4. Signal processor (nodes 6+7)
    try:
        sp = SignalProcessor("finale")
        sp.ingest(raw)
        stats = sp.compute_stats()
        results["processor_mean"] = stats["mean"]
    except Exception as e:
        errors.append(f"SignalProcessor: {e}")
    
    # 5. Generators (node 8+9)
    try:
        fibs = list(fibonacci_gen(8))
        results["fib_8"] = fibs[-1]
    except Exception as e:
        errors.append(f"fibonacci_gen: {e}")
    
    # 6. Safe division (node 10)
    try:
        divs = safe_divide_batch([(fibs[-1], 3)])
        results["fib_div_3"] = divs[0]["result"]
    except Exception as e:
        errors.append(f"safe_divide_batch: {e}")
    
    # 7. JSON round-trip (node 12)
    try:
        jr = json_stress_test()
        results["json_match"] = jr["match"]
    except Exception as e:
        errors.append(f"json_stress_test: {e}")
    
    # Summary
    passed = len(results)
    failed = len(errors)
    total = passed + failed
    
    print(f"\n{'='*50}")
    print(f"🏁 GRAND FINALE — Cross-Node Integration")
    print(f"{'='*50}")
    print(f"   Checks passed: {passed}/{total}")
    
    if errors:
        print(f"   ❌ Errors:")
        for e in errors:
            print(f"      • {e}")
    else:
        print(f"   ✅ ALL CLEAR — every prior node is reachable!")
    
    print(f"\n   Results: {json.dumps(results, indent=4, default=str)}")
    
    return {"passed": passed, "failed": failed, "results": results, "errors": errors}
