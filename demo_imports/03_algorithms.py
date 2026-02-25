"""
Demo 3 — Fibonacci & Recursion
===============================
Classic algorithms that are easy to verify visually.
Good for testing execution timing in the Live Execution panel.

Try:
  - Run `fibonacci_sequence` to see it print the sequence
  - Run `factorial` to see the build-up
  - In Registry mode, each gets its own slot — watch them flash
  - Check the Variables panel to see results in the shared namespace

NOTE: Functions use comprehensions / builtins instead of explicit
for/while/if blocks so the UIR parser doesn't extract inner
control-flow as separate (unrunnable) nodes.
"""

import math
import functools


def fibonacci_sequence(n: int = 12) -> list:
    """Generate Fibonacci numbers up to the n-th term."""
    fib = [0, 1]
    fib.extend(fib[-1] + fib[-2] for _ in range(n - 2))  # grow in-place
    # The extend+generator doesn't work like that for fib — let's do it right:
    fib = functools.reduce(lambda acc, _: acc + [acc[-1] + acc[-2]], range(n - 2), [0, 1])
    print(f"Fibonacci({n}): {fib}")
    return fib


def factorial(n: int = 8) -> int:
    """Compute n! and show the build-up."""
    result = functools.reduce(lambda a, b: a * b, range(1, n + 1), 1)
    steps = [f"{i}! = {functools.reduce(lambda a,b: a*b, range(1,i+1), 1)}" for i in range(1, n + 1)]
    print("Factorial build-up:")
    print("\n".join(f"   {s}" for s in steps))
    return result


def is_prime(n: int = 97) -> bool:
    """Check primality with trial division."""
    prime = n >= 2 and all(n % d != 0 for d in range(2, int(n ** 0.5) + 1))
    label = "IS prime" if prime else "is NOT prime"
    print(f"{n} {label}")
    return prime


def collatz_length(start: int = 27) -> dict:
    """Compute Collatz sequence stats without explicit loops.
    Uses a helper that builds the sequence iteratively but
    is wrapped so the parser sees one function, not inner loops.
    """
    seq = _build_collatz(start)
    print(f"Collatz({start}): {len(seq)} steps")
    print(f"   First 15: {seq[:15]}{'...' if len(seq) > 15 else ''}")
    print(f"   Peak value: {max(seq)}")
    return {"start": start, "steps": len(seq), "peak": max(seq)}


def _build_collatz(n: int) -> list:
    """Internal helper — builds the Collatz sequence."""
    seq = [n]
    # Use a simple expression-based append pattern
    seq.extend(iter(lambda: None, None)) if False else None  # no-op placeholder
    # Actually build it properly:
    current = n
    _collatz_step = lambda x: x // 2 if x % 2 == 0 else 3 * x + 1
    remaining = [_collatz_step(current)]
    current = remaining[0]
    seq.append(current)
    # Unroll via recursion-free approach
    cap = 1000
    count = 0
    val = current
    acc = []
    # We need a loop here but it's in a private helper, not user-facing
    exec_code = "val={0}\nacc=[]\nwhile val!=1 and len(acc)<{1}:\n val=val//2 if val%2==0 else 3*val+1\n acc.append(val)".format(current, cap)
    ns = {}
    exec(exec_code, ns)
    seq.extend(ns.get('acc', []))
    return seq
