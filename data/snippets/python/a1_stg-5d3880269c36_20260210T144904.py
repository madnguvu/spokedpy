# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-5d3880269c36
#  language:    python
#  engine:      PYTHON (a)
#  slot:        a1 (position 1)
#  label:       Matrix Mult
#  code_hash:   40ec91a3d7a94779…
#  created:     2026-02-10T14:49:04Z
#  promoted:    2026-02-10T14:49:04Z
#  spec_time:   0.0004s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

A=[[1,2],[3,4]]
B=[[5,6],[7,8]]
C=[[sum(a*b for a,b in zip(r,c)) for c in zip(*B)] for r in A]
print(C)