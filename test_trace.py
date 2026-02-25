"""Trace the promote flow step by step to find where the slot disappears."""
import urllib.request, json, sys

def spokedpy(method, path, body=None):
    url = f"http://localhost:5002{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        try:
            return json.loads(body_text), e.code
        except:
            return {"raw": body_text}, e.code

# ─── Step 1: Use the phased pipeline so we can inspect each stage ──────────

print("=== PHASED PIPELINE TRACE ===\n")

# Phase 1: Queue
print("1. QUEUE")
r, code = spokedpy("POST", "/api/staging/queue", {
    "engine_letter": "a",
    "language": "python",
    "code": "print('trace test')",
    "label": "trace_debug",
})
print(f"   HTTP {code}")
snip = r.get("snippet", {})
sid = snip.get("staging_id")
addr = snip.get("reserved_address")
print(f"   staging_id: {sid}")
print(f"   reserved_address: {addr}")
print(f"   reserved_engine: {snip.get('reserved_engine')}")
print(f"   reserved_position: {snip.get('reserved_position')}")
print(f"   phase: {snip.get('phase')}")

# Phase 2: Speculate
print("\n2. SPECULATE")
r, code = spokedpy("POST", f"/api/staging/speculate/{sid}")
snip = r.get("snippet", {})
print(f"   HTTP {code}")
print(f"   spec_success: {snip.get('spec_success')}")
print(f"   spec_output: {(snip.get('spec_output') or '').strip()}")
print(f"   phase: {snip.get('phase')}")

# Phase 3: Verdict
print("\n3. VERDICT")
r, code = spokedpy("POST", f"/api/staging/verdict/{sid}", {"action": "auto"})
snip = r.get("snippet", {})
print(f"   HTTP {code}")
print(f"   phase: {snip.get('phase')}")

# Phase 4: Promote
print("\n4. PROMOTE")
r, code = spokedpy("POST", f"/api/staging/promote/{sid}")
snip = r.get("snippet", {})
print(f"   HTTP {code}")
print(f"   phase: {snip.get('phase')}")
print(f"   registry_slot_id: {snip.get('registry_slot_id')}")
print(f"   ledger_node_id: {snip.get('ledger_node_id')}")
slot_id = snip.get("registry_slot_id", "")
print(f"   Full snippet keys: {list(snip.keys())}")

# ─── Now check if the slot actually exists ──────────────────────────

print(f"\n5. SLOT CHECK — GET /api/registry/slot/{slot_id}")
r, code = spokedpy("GET", f"/api/registry/slot/{slot_id}")
print(f"   HTTP {code}")
print(f"   Response: {json.dumps(r, indent=2)[:500]}")

# Check the matrix for Python row
print(f"\n6. MATRIX CHECK — Python engine row")
r, code = spokedpy("GET", "/api/registry/matrix")
py_engine = r.get("engines", {}).get("PYTHON", {})
py_slots = py_engine.get("slots", {})
occupied = {k: v for k, v in py_slots.items() if v is not None}
print(f"   Python slots occupied: {len(occupied)}")
if occupied:
    for k, v in list(occupied.items())[:5]:
        print(f"   Slot {k}: {json.dumps(v, indent=4)[:200]}")
else:
    print("   *** ALL PYTHON SLOTS ARE NULL ***")
    print("   This means commit_node() failed silently.")

# Check if the node exists in the ledger
print(f"\n7. SNIPPET DETAIL — GET /api/staging/snippet/{sid}")
r, code = spokedpy("GET", f"/api/staging/snippet/{sid}")
snip = r.get("snippet", {})
print(f"   phase: {snip.get('phase')}")
print(f"   ledger_node_id: {snip.get('ledger_node_id')}")
print(f"   registry_slot_id: {snip.get('registry_slot_id')}")
print(f"   saved_file_path: {snip.get('saved_file_path')}")

print("\n=== TRACE COMPLETE ===")
