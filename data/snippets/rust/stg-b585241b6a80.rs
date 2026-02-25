// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-b585241b6a80
//  language:    rust
//  engine:      RUST (d)
//  slot:        d2 (position 2)
//  label:       Factorial
//  code_hash:   58b38b0d91ea1b4a…
//  created:     2026-02-10T10:51:04Z
//  promoted:    2026-02-10T10:51:07Z
//  spec_time:   2.8998s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

fn factorial(n: u64) -> u64 {
    if n <= 1 { 1 } else { n * factorial(n-1) }
}
fn main() {
    println!("{}", factorial(10));
}