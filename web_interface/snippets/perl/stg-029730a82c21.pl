# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-029730a82c21
#  language:    perl
#  engine:      PERL (o)
#  slot:        o1 (position 1)
#  label:       test_perl_primes
#  code_hash:   a3a4de912b2fe8bb…
#  created:     2026-02-09T02:36:59Z
#  promoted:    2026-02-09T02:36:59Z
#  spec_time:   0.2733s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

use strict;
use warnings;
my @primes;
OUTER: for my $n (2..30) {
    for my $d (2..int(sqrt($n))) {
        next OUTER if $n % $d == 0;
    }
    push @primes, $n;
}
print "Primes to 30: @primes\n";
