// ═══════════════════════════════════════════════════════
//  VPyD Staged Snippet — PROMOTED TO PRODUCTION
//  staging_id:  stg-3ef756111624
//  language:    c
//  engine:      C (m)
//  slot:        m3 (position 3)
//  label:       Sum Array
//  code_hash:   4fa554c87c54e7fb…
//  created:     2026-02-10T08:35:44Z
//  promoted:    2026-02-10T08:35:46Z
//  spec_time:   1.4919s
//  spec_result: PASS
// ═══════════════════════════════════════════════════════

#include <stdio.h>
int main() {
    int a[]={1,2,3,4,5}, s=0;
    for(int i=0;i<5;i++) s+=a[i];
    printf("%d\n",s);
    return 0;
}