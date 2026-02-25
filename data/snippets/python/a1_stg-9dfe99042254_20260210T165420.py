# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-9dfe99042254
#  language:    python
#  engine:      PYTHON (a)
#  slot:        a1 (position 1)
#  label:       Fibonacci
#  code_hash:   7a922002b1fb4cb5…
#  created:     2026-02-10T16:54:20Z
#  promoted:    2026-02-10T16:54:20Z
#  spec_time:   0.0003s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

def fib(n):
    a,b=0,1
    for _ in range(n): a,b=b,a+b
    return a
print(fib(10))