// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-55ce4f44ddcf
//  language:    rust
//  engine:      RUST (d)
//  slot:        d2 (position 2)
//  label:       Factorial
//  code_hash:   58b38b0d91ea1b4a…
//  created:     2026-02-10T08:34:12Z
//  promoted:    2026-02-10T08:34:13Z
//  spec_time:   1.4463s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

fn factorial(n: u64) -> u64 {
    if n <= 1 { 1 } else { n * factorial(n-1) }
}
fn main() {
    println!("{}", factorial(10));
}