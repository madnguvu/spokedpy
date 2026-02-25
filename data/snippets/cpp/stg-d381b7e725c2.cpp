// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-d381b7e725c2
//  language:    cpp
//  engine:      CPP (g)
//  slot:        g5 (position 5)
//  label:       Factorial
//  code_hash:   e4530f779867c0a1…
//  created:     2026-02-10T10:51:36Z
//  promoted:    2026-02-10T10:51:37Z
//  spec_time:   1.5324s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

#include <iostream>
int fact(int n) { return n<=1 ? 1 : n*fact(n-1); }
int main() { std::cout << fact(10) << std::endl; return 0; }