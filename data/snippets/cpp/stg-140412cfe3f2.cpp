// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-140412cfe3f2
//  language:    cpp
//  engine:      CPP (g)
//  slot:        g6 (position 6)
//  label:       Vector Sum
//  code_hash:   c4fb908389ac1c9f…
//  created:     2026-02-10T10:51:39Z
//  promoted:    2026-02-10T10:51:41Z
//  spec_time:   1.8619s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

#include <iostream>
#include <vector>
#include <numeric>
int main() {
    std::vector<int> v={1,2,3,4,5};
    std::cout << std::accumulate(v.begin(),v.end(),0) << std::endl;
    return 0;
}