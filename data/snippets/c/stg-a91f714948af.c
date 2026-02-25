// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-a91f714948af
//  language:    c
//  engine:      C (m)
//  slot:        m2 (position 2)
//  label:       Factorial
//  code_hash:   60fb0ca4636f097d…
//  created:     2026-02-10T08:35:41Z
//  promoted:    2026-02-10T08:35:42Z
//  spec_time:   1.4568s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

#include <stdio.h>
int fact(int n) { return n<=1 ? 1 : n*fact(n-1); }
int main() { printf("%d\n", fact(10)); return 0; }