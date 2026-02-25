# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-739426e47b1c
#  language:    python
#  engine:      PYTHON (a)
#  slot:        a1 (position 1)
#  label:       test_fibonacci
#  code_hash:   97bd981234eec8e4…
#  created:     2026-02-09T02:36:47Z
#  promoted:    2026-02-09T02:36:47Z
#  spec_time:   0.0003s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print(fibonacci(10))
