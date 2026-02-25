# ═══════════════════════════════════════════════════════
#  VPyD Staged Snippet — PROMOTED TO PRODUCTION
#  staging_id:  stg-350299f727f9
#  language:    python
#  engine:      PYTHON (a)
#  slot:        a1 (position 1)
#  label:       Python — System Profiler
#  code_hash:   22de23c0c2f5be5e…
#  created:     2026-02-09T02:18:29Z
#  promoted:    2026-02-09T02:18:41Z
#  spec_time:   11.8511s
#  spec_result: PASS
# ═══════════════════════════════════════════════════════

# ━━━ SpokedPy Python Engine ━━━
# System performance profiler — real hardware metrics

import platform, os, sys, time, subprocess
from datetime import datetime

print('=' * 48)
print('  SpokedPy — Python System Profiler')
print('=' * 48)

# Platform info
print(f'  OS          : {platform.system()} {platform.release()}')
print(f'  Machine     : {platform.machine()}')
print(f'  Node        : {platform.node()}')
print(f'  Python      : {sys.version.split()[0]}')
print(f'  CPU cores   : {os.cpu_count()}')

# Memory via OS commands (cross-platform)
try:
    if platform.system() == 'Windows':
        r = subprocess.run(
            ['wmic', 'OS', 'get', 'FreePhysicalMemory,TotalVisibleMemorySize', '/value'],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in r.stdout.strip().split('\n') if '=' in l]
        mem = {}
        for l in lines:
            k, v = l.split('=')
            mem[k] = int(v)  # KB
        total_mb = mem.get('TotalVisibleMemorySize', 0) / 1024
        free_mb  = mem.get('FreePhysicalMemory', 0) / 1024
        used_mb  = total_mb - free_mb
        pct      = (used_mb / total_mb * 100) if total_mb else 0
        print(f'  RAM total   : {total_mb:,.0f} MB')
        print(f'  RAM used    : {used_mb:,.0f} MB ({pct:.1f}%)')
        print(f'  RAM free    : {free_mb:,.0f} MB')
    else:
        import shutil
        total, used, free = shutil.disk_usage('/')
        print(f'  Disk total  : {total // (1024**3)} GB')
except Exception as e:
    print(f'  Memory info : unavailable ({e})')

# CPU benchmark — measure SpokedPy's own impact
print('-' * 48)
print('  CPU Benchmark (running inside SpokedPy):')

t0 = time.perf_counter()
total = 0
for i in range(1_000_000):
    total += i * i
elapsed = time.perf_counter() - t0

print(f'  1M iterations : {elapsed:.4f}s')
print(f'  Throughput    : {1_000_000/elapsed:,.0f} ops/sec')
print(f'  Checksum      : {total % 999_999_937}')

# Process count
try:
    if platform.system() == 'Windows':
        r = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'],
                          capture_output=True, text=True, timeout=5)
        proc_count = len([l for l in r.stdout.strip().split('\n') if l.strip()])
    else:
        r = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
        proc_count = len(r.stdout.strip().split('\n')) - 1
    print(f'  Processes   : {proc_count} running')
except Exception:
    pass

print('-' * 48)
print(f'  Timestamp   : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('  Status      : SpokedPy monitoring itself')
print('=' * 48)