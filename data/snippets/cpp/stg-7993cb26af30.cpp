// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-7993cb26af30
//  language:    cpp
//  engine:      CPP (g)
//  slot:        g3 (position 3)
//  label:       Vector Sum
//  code_hash:   c4fb908389ac1c9f…
//  created:     2026-02-10T08:34:46Z
//  promoted:    2026-02-10T08:34:51Z
//  spec_time:   4.8219s
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