# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-b46354a33397
#  language:    python
#  engine:      PYTHON (a)
#  slot:        a2 (position 2)
#  label:       Prime Sieve
#  code_hash:   20ef8b62d3bd1b5c…
#  created:     2026-02-10T08:01:25Z
#  promoted:    2026-02-10T08:01:25Z
#  spec_time:   0.0020s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

def sieve(n):
    s=set(range(2,n+1))
    for i in range(2,int(n**0.5)+1):
        s-=set(range(i*2,n+1,i))
    return sorted(s)
print(sieve(30))