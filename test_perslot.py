"""Test per-slot execution endpoint."""
import requests, json, sys

BASE = "http://localhost:5002"

# 1) Check matrix first
print("=== Matrix Status ===")
r = requests.get(f"{BASE}/api/registry/matrix")
if r.status_code != 200:
    print(f"Matrix endpoint failed: {r.status_code}")
    sys.exit(1)

matrix = r.json()
engines = matrix.get("engines", {})
total_slots = 0
for ename, edata in engines.items():
    slots = edata.get("slots", {})
    filled = sum(1 for v in slots.values() if v is not None)
    if filled:
        print(f"  {edata.get('letter','?')} {ename:12s} lang={edata.get('language','?'):12s}  {filled}/{edata.get('max_slots',3)} slots filled")
        total_slots += filled

print(f"\nTotal filled slots: {total_slots}")

if total_slots == 0:
    print("\n*** No slots committed. Run load_grid.py first. ***")
    sys.exit(0)

# 2) Run per-slot execution
print("\n=== Per-Slot Execution ===")
r = requests.post(f"{BASE}/api/execution/registry/run-all-slots", json={})
if r.status_code != 200:
    print(f"Per-slot endpoint failed: {r.status_code} {r.text[:200]}")
    sys.exit(1)

data = r.json()
summary = data.get("summary", {})
results = data.get("results", [])

print(f"Total slots executed: {summary.get('total_slots', 0)}")
print(f"  Passed: {summary.get('passed', 0)}")
print(f"  Failed: {summary.get('failed', 0)}")
print(f"  Skipped: {summary.get('skipped', 0)}")

# 3) Show results per slot
print("\n=== Results Detail ===")
for res in sorted(results, key=lambda x: x.get("address", "")):
    addr = res.get("address", "???")
    lang = res.get("language", "???")
    ok = res.get("success", False)
    err = res.get("error", "")
    output = res.get("output", "")
    status = "PASS" if ok else "FAIL"
    
    # Truncate output/error for display
    detail = ""
    if not ok and err:
        detail = f"  ERR: {err[:120]}"
    elif ok and output:
        # Show first line of output
        first_line = output.strip().split("\n")[0][:80]
        detail = f"  OUT: {first_line}"
    
    print(f"  {addr:5s} {lang:12s} {status}  {detail}")

# 4) Specifically check compiled languages with main()
print("\n=== Compiled Languages (main() conflict test) ===")
compiled_langs = {"rust", "cpp", "c", "go", "java"}
for res in sorted(results, key=lambda x: x.get("address", "")):
    lang = res.get("language", "")
    if lang in compiled_langs:
        addr = res.get("address", "???")
        ok = res.get("success", False)
        err = res.get("error", "")
        output = res.get("output", "")
        
        has_dup_main = "multiple definition" in err.lower() or "redefinition" in err.lower() or "duplicate symbol" in err.lower()
        
        if has_dup_main:
            print(f"  {addr} {lang}: *** DUPLICATE MAIN BUG STILL PRESENT ***")
        elif not ok:
            print(f"  {addr} {lang}: FAIL (other reason): {err[:100]}")
        else:
            print(f"  {addr} {lang}: PASS - independent execution confirmed")

print("\nDone.")
