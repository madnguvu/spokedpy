"""Quick debug test — isolate the push failure."""
import urllib.request, json

def spokedpy(method, path, body=None):
    url = f"http://localhost:5002{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body}")
        return json.loads(body) if body.startswith('{') else {"error": body}, e.code

# Step 1: Create a slot
print("1. Creating slot...")
r, code = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "a",
    "language": "python",
    "code": "print('push test')",
    "label": "push_debug",
    "auto_promote": True,
})
snip = r.get("snippet", {})
slot_id = snip.get("registry_slot_id", "")
print(f"   Phase: {snip.get('phase')}, Slot: {slot_id}")

# Step 2: Check slot details
print(f"\n2. Checking slot {slot_id}...")
r, code = spokedpy("GET", f"/api/registry/slot/{slot_id}")
slot = r.get("slot", {})
print(f"   Active: {slot.get('is_active')}")
print(f"   Permissions: {slot.get('permissions')}")

# Step 3: Try push
print(f"\n3. Pushing to {slot_id}...")
r, code = spokedpy("POST", f"/api/registry/slot/{slot_id}/push", {
    "data": {"items": [1, 2, 3]},
    "source_slot": "test",
})
print(f"   Status: {code}, Response: {r}")

# Step 4: Try output buffer
print(f"\n4. Reading output buffer for {slot_id}...")
r, code = spokedpy("GET", f"/api/registry/slot/{slot_id}/output?last_n=5")
print(f"   Status: {code}, Response: {json.dumps(r, indent=2)}")
