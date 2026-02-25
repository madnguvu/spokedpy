// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-78799aaf83be
//  language:    rust
//  engine:      RUST (d)
//  slot:        d3 (position 3)
//  label:       Fibonacci
//  code_hash:   ffb1e00cf418e2b6…
//  created:     2026-02-10T10:51:09Z
//  promoted:    2026-02-10T10:51:10Z
//  spec_time:   1.5364s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

fn fib(n: u32) -> u64 {
    let (mut a, mut b) = (0u64, 1u64);
    for _ in 0..n { let t = a + b; a = b; b = t; }
    a
}
fn main() {
    println!("{}", fib(20));
}