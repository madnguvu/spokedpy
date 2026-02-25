# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-1eff746c636f
#  language:    python
#  engine:      PYTHON (a)
#  slot:        a1 (position 1)
#  label:       Matrix Mult
#  code_hash:   40ec91a3d7a94779…
#  created:     2026-02-10T11:57:14Z
#  promoted:    2026-02-10T11:57:14Z
#  spec_time:   0.0014s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

A=[[1,2],[3,4]]
B=[[5,6],[7,8]]
C=[[sum(a*b for a,b in zip(r,c)) for c in zip(*B)] for r in A]
print(C)