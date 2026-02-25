"""End-to-end test of the Marshal Token API."""
import urllib.request, json, time

BASE = "http://localhost:5002"

def api(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

print("=" * 60)
print("TEST 1: Submit code via POST /api/marshal")
print("=" * 60)
status, data = api("POST", "/api/marshal", {
    "engine_letter": "a",
    "language": "python",
    "code": "print('Hello from the marshal gateway!')",
    "label": "marshal_test_1",
    "auto_promote": True
})
print(f"  HTTP {status}")
print(f"  Token:       {data.get('token')}")
print(f"  Phase:       {data.get('phase')}")
print(f"  TTL:         {data.get('ttl')}s")
print(f"  Exec Time:   {data.get('execution_time')}s")
print(f"  Output:      {data.get('output', '').strip()}")
print(f"  Endpoints:   {json.dumps(data.get('endpoints', {}), indent=4)}")

token = data.get("token")
if not token:
    print("\n*** No token returned — aborting remaining tests ***")
    exit(1)

print()
print("=" * 60)
print(f"TEST 2: Quick status poll — GET /api/marshal/{token}/status")
print("=" * 60)
status, data = api("GET", f"/api/marshal/{token}/status")
print(f"  HTTP {status}")
print(f"  Full response:")
print(f"  {json.dumps(data, indent=4)}")

print()
print("=" * 60)
print(f"TEST 3: Full details — GET /api/marshal/{token}")
print("=" * 60)
status, data = api("GET", f"/api/marshal/{token}")
print(f"  HTTP {status}")
print(f"  Full response:")
print(f"  {json.dumps(data, indent=4)}")

print()
print("=" * 60)
print("TEST 4: Bad token — GET /api/marshal/m-doesnotexist")
print("=" * 60)
status, data = api("GET", "/api/marshal/m-doesnotexist")
print(f"  HTTP {status}")
print(f"  Error:  {data.get('error')}")

print()
print("=" * 60)
print("TEST 5: Bad request — POST /api/marshal with missing fields")
print("=" * 60)
status, data = api("POST", "/api/marshal", {"language": "python"})
print(f"  HTTP {status}")
print(f"  Error:  {data.get('error')}")

print()
print("=" * 60)
print("ALL MARSHAL TESTS COMPLETE")
print("=" * 60)
