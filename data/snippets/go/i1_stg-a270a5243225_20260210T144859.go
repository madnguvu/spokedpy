// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-a270a5243225
//  language:    go
//  engine:      GO (i)
//  slot:        i1 (position 1)
//  label:       Fibonacci
//  code_hash:   adf8bbb5993bf7ae…
//  created:     2026-02-10T14:48:58Z
//  promoted:    2026-02-10T14:48:59Z
//  spec_time:   1.1118s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

package main
import "fmt"
func fib(n int) int {
    a, b := 0, 1
    for i := 0; i < n; i++ { a, b = b, a+b }
    return a
}
func main() { fmt.Println(fib(10)) }