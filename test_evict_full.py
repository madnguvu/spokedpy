"""Full eviction test — verifies the node is purged from registry AND ledger.

Tests:
  1. Evict returns success
  2. Registry matrix no longer shows the slot
  3. Ledger no longer lists the node as active
  4. commit-all does NOT resurrect the node
  5. hydrate-slots does NOT include the node
  6. run-all-slots does NOT execute the evicted node
"""
import requests, json, sys

BASE = "http://localhost:5002"

def get_matrix_slots():
    r = requests.get(f"{BASE}/api/registry/matrix")
    d = r.json()
    slots = {}
    for ename, edata in d.get('engines', {}).items():
        for pos, sdata in edata.get('slots', {}).items():
            if sdata and sdata.get('node_id'):
                addr = f"{edata['letter']}{pos}"
                slots[addr] = sdata
    return slots

def get_active_ledger_nodes():
    r = requests.get(f"{BASE}/api/execution/ledger/nodes")
    d = r.json()
    return {n['node_id']: n for n in d.get('nodes', [])} if d.get('success') else {}


# ─── Setup ───
before_slots = get_matrix_slots()
before_nodes = get_active_ledger_nodes()
print(f"BEFORE: {len(before_slots)} registry slots, {len(before_nodes)} ledger nodes")

if not before_slots:
    print("No slots to test! Run load_grid.py first.")
    sys.exit(1)

# Pick a target slot
target_addr = sorted(before_slots.keys())[0]
target_slot = before_slots[target_addr]
target_node_id = target_slot['node_id']
target_slot_id = target_slot.get('slot_id', '')
print(f"\nTarget: {target_addr.upper()} | node={target_node_id} | slot_id={target_slot_id}")

# Confirm it's in the ledger
if target_node_id in before_nodes:
    print(f"  Ledger: YES — node is active in ledger")
else:
    print(f"  Ledger: NOT FOUND (unusual, but testing anyway)")

# ─── Test 1: Evict ───
print(f"\n{'='*60}")
print(f"TEST 1: Evicting {target_addr.upper()}...")
r = requests.delete(f"{BASE}/api/registry/slot/{target_addr}/evict")
resp = r.json()
assert resp.get('success'), f"Evict failed: {resp}"
print(f"  Result: success={resp['success']}, ledger_deleted={resp.get('ledger_deleted')}, token_revoked={resp.get('token_revoked')}")

# ─── Test 2: Registry ───
print(f"\nTEST 2: Registry check...")
after_slots = get_matrix_slots()
if target_addr in after_slots:
    print(f"  FAIL: {target_addr} still in registry!")
    sys.exit(1)
else:
    print(f"  PASS: {target_addr} removed from registry ({len(before_slots)} -> {len(after_slots)})")

# ─── Test 3: Ledger ───
print(f"\nTEST 3: Ledger check...")
after_nodes = get_active_ledger_nodes()
if target_node_id in after_nodes:
    print(f"  FAIL: {target_node_id} still active in ledger!")
    sys.exit(1)
else:
    print(f"  PASS: {target_node_id} no longer active in ledger ({len(before_nodes)} -> {len(after_nodes)})")

# ─── Test 4: commit-all doesn't resurrect ───
print(f"\nTEST 4: commit-all resurrection check...")
r = requests.post(f"{BASE}/api/registry/commit-all")
d = r.json()
print(f"  commit-all returned: committed={d.get('committed', '?')}")
post_commit_slots = get_matrix_slots()
if target_addr in post_commit_slots:
    print(f"  FAIL: {target_addr} was resurrected by commit-all!")
    sys.exit(1)
else:
    print(f"  PASS: {target_addr} NOT resurrected ({len(post_commit_slots)} slots)")

# ─── Test 5: hydrate-slots doesn't include evicted ───
print(f"\nTEST 5: hydrate-slots check...")
r = requests.get(f"{BASE}/api/execution/registry/hydrate-slots")
d = r.json()
hydrated_addrs = [t.get('address') for t in d.get('tabs', [])]
if target_addr in hydrated_addrs:
    print(f"  FAIL: {target_addr} appeared in hydrate-slots!")
    sys.exit(1)
else:
    print(f"  PASS: {target_addr} NOT in hydrate-slots ({len(hydrated_addrs)} tabs)")

# ─── Test 6: run-all-slots doesn't execute evicted ───
print(f"\nTEST 6: run-all-slots check...")
r = requests.post(f"{BASE}/api/execution/registry/run-all-slots", json={})
d = r.json()
executed_addrs = [res.get('address') for res in d.get('results', [])]
if target_addr in executed_addrs:
    print(f"  FAIL: {target_addr} was executed by run-all-slots!")
    sys.exit(1)
else:
    total = d.get('summary', {}).get('total_slots', 0)
    passed = d.get('summary', {}).get('passed', 0)
    print(f"  PASS: {target_addr} NOT executed ({total} slots ran, {passed} passed)")

print(f"\n{'='*60}")
print(f"ALL TESTS PASSED — eviction is complete and permanent")
print(f"  Registry: {target_addr} gone")
print(f"  Ledger: {target_node_id} deleted")
print(f"  No resurrection via commit-all")
print(f"  No ghost in hydrate or execution")
