// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-9d9373c23a37
//  language:    go
//  engine:      GO (i)
//  slot:        i1 (position 1)
//  label:       test_go_squares
//  code_hash:   536800df63b45b0c…
//  created:     2026-02-09T02:36:56Z
//  promoted:    2026-02-09T02:36:57Z
//  spec_time:   0.8377s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

package main

import "fmt"

func main() {
    for i := 1; i <= 5; i++ {
        fmt.Printf("%d squared = %d\n", i, i*i)
    }
}