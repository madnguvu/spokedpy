// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-4ed52382cd26
//  language:    cpp
//  engine:      CPP (g)
//  slot:        g2 (position 2)
//  label:       Factorial
//  code_hash:   e4530f779867c0a1…
//  created:     2026-02-10T08:34:42Z
//  promoted:    2026-02-10T08:34:44Z
//  spec_time:   2.1560s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

#include <iostream>
int fact(int n) { return n<=1 ? 1 : n*fact(n-1); }
int main() { std::cout << fact(10) << std::endl; return 0; }