"""Test evict endpoint — does it actually remove a slot?"""
import requests, json

BASE = "http://localhost:5002"

def get_slot_count():
    r = requests.get(f"{BASE}/api/registry/matrix")
    d = r.json()
    total = 0
    slot_addrs = []
    for ename, edata in d.get('engines', {}).items():
        for pos, sdata in edata.get('slots', {}).items():
            if sdata and sdata.get('node_id'):
                addr = f"{edata['letter']}{pos}"
                slot_addrs.append(addr)
                total += 1
    return total, sorted(slot_addrs)

# 1) Show before state
before_count, before_addrs = get_slot_count()
print(f"BEFORE: {before_count} occupied slots")
print(f"  Slots: {before_addrs[:10]}{'...' if len(before_addrs) > 10 else ''}")

# 2) Pick a slot to evict (first one found)
target = before_addrs[0] if before_addrs else None
if not target:
    print("No slots to evict!")
    exit(1)

print(f"\nEvicting slot: {target}")
r = requests.delete(f"{BASE}/api/registry/slot/{target}/evict")
print(f"  HTTP {r.status_code}")
resp = r.json()
print(f"  Response: {json.dumps(resp, indent=2)}")

# 3) Show after state
after_count, after_addrs = get_slot_count()
print(f"\nAFTER: {after_count} occupied slots")
print(f"  Slots: {after_addrs[:10]}{'...' if len(after_addrs) > 10 else ''}")

# 4) Verdict
if after_count == before_count - 1 and target not in after_addrs:
    print(f"\n*** EVICTION WORKS: slot {target} removed, count {before_count} -> {after_count} ***")
elif target not in after_addrs:
    print(f"\n*** SLOT REMOVED but count mismatch: {before_count} -> {after_count} ***")
else:
    print(f"\n*** EVICTION FAILED: slot {target} still present! Count: {before_count} -> {after_count} ***")

# 5) Also check enriched matrix
print("\nChecking enriched matrix for evicted slot...")
r = requests.get(f"{BASE}/api/registry/matrix/enriched")
d = r.json()
engines = d.get('engines', {})
letter = target[0]
pos = target[1:]
for ename, edata in engines.items():
    if edata.get('letter') == letter:
        slot_val = edata.get('slots', {}).get(pos)
        if slot_val and slot_val.get('node_id'):
            print(f"  ENRICHED MATRIX: {target} STILL has node_id={slot_val['node_id']}!")
            print(f"  *** GHOST DATA — this is the bug ***")
        else:
            print(f"  ENRICHED MATRIX: {target} correctly shows empty/None")
        break
