"""
Demo 1 — Hello World
=====================
The simplest possible demo. Import this file to see a single function
appear in the Live Execution panel.

Try:
  1. Open Live Execution (⚡ button)
  2. Click "Refresh" to load nodes from the ledger
  3. Select `greet` → click "Run"
  4. Flip the toggle to "Registry" mode and run again
     — watch slot a1 light up in the Engine Matrix grid!
"""


def greet(name: str = "SpokedPy") -> str:
    """Return a friendly greeting."""
    message = f"Hello, {name}! Welcome to the visual programming matrix."
    print(message)
    return message


def count_to(n: int = 5) -> list:
    """Count from 1 to n and return the list."""
    numbers = list(range(1, n + 1))
    print(f"Counting: {numbers}")
    return numbers
