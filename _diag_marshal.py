"""Quick diagnostic — does the running server have the marshal routes?"""
import urllib.request, json

def check(method, url):
    req = urllib.request.Request(url, method=method)
    if method == "POST":
        req.data = json.dumps({"test": True}).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  {method} {url} => {resp.status}")
            print(f"    Body: {resp.read().decode()[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  {method} {url} => HTTP {e.code}")
        print(f"    Body: {body[:300]}")

# Check if marshal routes exist at all vs generic Flask 404
print("=== Marshal Route Diagnostics ===")
check("GET", "http://localhost:5002/api/marshal/m-fake")
print()
check("GET", "http://localhost:5002/api/marshal/m-fake/status")
print()
check("GET", "http://localhost:5002/api/totally-nonexistent-route")
print()

# Now do a submit and immediately check the token
print("=== Submit + Immediate Lookup ===")
payload = json.dumps({
    "engine_letter": "a",
    "language": "python",
    "code": "print('token test')",
    "label": "diag_token",
    "auto_promote": True
}).encode()
req = urllib.request.Request(
    "http://localhost:5002/api/marshal",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    token = data.get("token")
    print(f"  POST /api/marshal => token={token}, phase={data.get('phase')}")

# Immediate GET
print(f"\n  Immediate lookup of {token}:")
check("GET", f"http://localhost:5002/api/marshal/{token}")
print(f"\n  Immediate status of {token}:")
check("GET", f"http://localhost:5002/api/marshal/{token}/status")
