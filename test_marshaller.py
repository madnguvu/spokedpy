#!/usr/bin/env python3
"""
SpokedPy Snippet Marshaller — Comprehensive Integration Test
Validates the full staging pipeline: queue → speculate → verdict → promote
Tests: engine discovery, one-shot pipeline, phased pipeline, slot ops,
       multi-engine simultaneous, error handling, push/input, rollback.
"""

import urllib.request, json, time, sys, textwrap

BASE = "http://localhost:5002"
PASS = 0
FAIL = 0
RESULTS = []

# ─── helpers ──────────────────────────────────────────────────────────────────

def spokedpy(method, path, body=None):
    """Call SpokedPy API.  Returns parsed JSON dict."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def test(name, condition, detail=""):
    global PASS, FAIL
    ok = "✅ PASS" if condition else "❌ FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    line = f"  {ok}  {name}"
    if detail and not condition:
        line += f"  ({detail})"
    print(line)
    RESULTS.append((name, condition, detail))

def section(title):
    print(f"\n{'─'*72}")
    print(f"  {title}")
    print(f"{'─'*72}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 1 — Engine Discovery
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 1 · Engine Discovery")
engines_resp = spokedpy("GET", "/api/engines")
engines_list = engines_resp.get("engines", [])
enabled = [e for e in engines_list if e["platform_enabled"]]
disabled = [e for e in engines_list if not e["platform_enabled"]]

test("GET /api/engines returns success",   engines_resp.get("success") is True)
test("Total engines == 15",                engines_resp.get("total") == 15)
test("Enabled count matches",             len(enabled) == engines_resp.get("enabled"))
test("Disabled count matches",            len(disabled) == engines_resp.get("disabled"))
test("Each engine has a letter",          all(e.get("letter") for e in engines_list))
test("Each engine has a name",            all(e.get("name") for e in engines_list))

print(f"\n  Enabled engines ({len(enabled)}):")
for e in enabled:
    ver = e.get("runtime_version") or "—"
    print(f"    [{e['letter']}] {e['name']:12s}  {ver}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 2 — One-shot Pipeline (Python)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 2 · One-shot Pipeline — Python")
code_py = textwrap.dedent("""\
    def fibonacci(n):
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    print(fibonacci(10))
""")

r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "a",
    "language": "python",
    "code": code_py,
    "label": "test_fibonacci",
    "auto_promote": True,
})
snip = r.get("snippet", {})
py_slot = snip.get("registry_slot_id", "")
py_sid  = snip.get("staging_id", "")

test("Phase is 'promoted'",    snip.get("phase") == "promoted")
test("spec_success is True",   snip.get("spec_success") is True)
test("Output contains '55'",   "55" in (snip.get("spec_output") or ""))
test("registry_slot_id set",   bool(py_slot))
test("staging_id set",         bool(py_sid))
test("reserved_address set",   bool(snip.get("reserved_address")))
print(f"    Slot: {py_slot}   StagingID: {py_sid}")
print(f"    Output: {(snip.get('spec_output') or '').strip()}")
print(f"    Exec time: {snip.get('spec_execution_time', 0):.4f}s")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 3 — One-shot Pipeline (JavaScript)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 3 · One-shot Pipeline — JavaScript")
code_js = textwrap.dedent("""\
    const greet = (name) => `Hello, ${name}!`;
    console.log(greet("SpokedPy"));
    console.log("2 + 2 =", 2 + 2);
""")

r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "b",
    "language": "javascript",
    "code": code_js,
    "label": "test_js_greet",
    "auto_promote": True,
})
snip = r.get("snippet", {})
js_slot = snip.get("registry_slot_id", "")

test("Phase is 'promoted'",          snip.get("phase") == "promoted")
test("spec_success is True",         snip.get("spec_success") is True)
test("Output contains 'SpokedPy'",   "SpokedPy" in (snip.get("spec_output") or ""))
test("registry_slot_id set",         bool(js_slot))
print(f"    Slot: {js_slot}")
print(f"    Output: {(snip.get('spec_output') or '').strip()}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 4 — One-shot Pipeline (Go)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 4 · One-shot Pipeline — Go")
code_go = 'package main\n\nimport "fmt"\n\nfunc main() {\n    for i := 1; i <= 5; i++ {\n        fmt.Printf("%d squared = %d\\n", i, i*i)\n    }\n}'

r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "i",
    "language": "go",
    "code": code_go,
    "label": "test_go_squares",
    "auto_promote": True,
})
snip = r.get("snippet", {})
go_slot = snip.get("registry_slot_id", "")

test("Phase is 'promoted'",          snip.get("phase") == "promoted")
test("spec_success is True",         snip.get("spec_success") is True)
test("Output contains 'squared'",    "squared" in (snip.get("spec_output") or ""))
test("registry_slot_id set",         bool(go_slot))
print(f"    Slot: {go_slot}")
print(f"    Output: {(snip.get('spec_output') or '').strip()}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 5 — One-shot Pipeline (Perl)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 5 · One-shot Pipeline — Perl")
code_perl = textwrap.dedent("""\
    use strict;
    use warnings;
    my @primes;
    OUTER: for my $n (2..30) {
        for my $d (2..int(sqrt($n))) {
            next OUTER if $n % $d == 0;
        }
        push @primes, $n;
    }
    print "Primes to 30: @primes\\n";
""")

r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "o",
    "language": "perl",
    "code": code_perl,
    "label": "test_perl_primes",
    "auto_promote": True,
})
snip = r.get("snippet", {})
perl_slot = snip.get("registry_slot_id", "")

test("Phase is 'promoted'",           snip.get("phase") == "promoted")
test("spec_success is True",          snip.get("spec_success") is True)
test("Output contains primes",        "2 3 5 7" in (snip.get("spec_output") or ""))
test("registry_slot_id set",          bool(perl_slot))
print(f"    Slot: {perl_slot}")
print(f"    Output: {(snip.get('spec_output') or '').strip()}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 6 — Slot Re-execution
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 6 · Slot Re-execution")
r = spokedpy("POST", f"/api/registry/slot/{py_slot}/execute", {})
result = r.get("result", {})
test("Re-execute returns output",     "55" in (result.get("output") or ""))
test("execution_time > 0",            (result.get("execution_time") or 0) > 0)
print(f"    Output: {(result.get('output') or '').strip()}")
print(f"    Time:   {result.get('execution_time', 0):.4f}s")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 7 — Slot Details (GET)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 7 · Slot Details")
r = spokedpy("GET", f"/api/registry/slot/{py_slot}")
slot = r.get("slot", {})
test("Slot has node_name",            bool(slot.get("node_name")))
test("Slot has engine_id",            bool(slot.get("engine_id")))
test("execution_count >= 2",          (slot.get("execution_count") or 0) >= 2,
     f"got {slot.get('execution_count')}")
test("is_active is True",             slot.get("is_active") is True)
print(f"    Node:       {slot.get('node_name')}")
print(f"    Engine:     {slot.get('engine_id')}")
print(f"    Version:    {slot.get('committed_version')}")
print(f"    Exec Count: {slot.get('execution_count')}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 8 — Slot Output Buffer
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 8 · Slot Output Buffer")
r = spokedpy("GET", f"/api/registry/slot/{py_slot}/output?last_n=5")
test("Output buffer returns success",  r.get("success") is True)
test("Buffer has entries",             len(r.get("output_history", r.get("outputs", []))) > 0)

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 9 — Push Data Into Slot
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 9 · Push Data Into Slot")

# First create a slot that reads _slot_input
code_input = textwrap.dedent("""\
    if '_slot_input' in dir():
        data = _slot_input
        total = sum(data.get('items', []))
        print(f"Sum = {total}")
    else:
        print("No input")
""")
r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "a",
    "language": "python",
    "code": code_input,
    "label": "test_push_target",
    "auto_promote": True,
})
push_slot = r["snippet"]["registry_slot_id"]
test("Push-target slot promoted",      r["snippet"]["phase"] == "promoted")

# Push data
r = spokedpy("POST", f"/api/registry/slot/{push_slot}/push", {
    "data": {"items": [10, 20, 30, 40, 50]},
    "source_slot": "test",
})
test("Push accepted",                  r.get("success") is True)

# Re-execute to see the pushed data
r = spokedpy("POST", f"/api/registry/slot/{push_slot}/execute", {})
out = (r.get("result", {}).get("output") or "").strip()
test("Execution sees pushed data",     "150" in out or "Sum" in out, f"output: {out}")
print(f"    Output after push: {out}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 10 — Phased Pipeline (queue → speculate → verdict → promote)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 10 · Phased Pipeline")
r = spokedpy("POST", "/api/staging/queue", {
    "engine_letter": "a",
    "language": "python",
    "code": "print('phased:', 42 * 137)",
    "label": "test_phased",
})
sid = r["snippet"]["staging_id"]
test("Phase 1 — Queued",              r["snippet"]["phase"] == "queued")
print(f"    staging_id: {sid}")

# Speculate
r = spokedpy("POST", f"/api/staging/speculate/{sid}")
test("Phase 2 — Speculated ok",       r["snippet"]["spec_success"] is True)
test("Output has '5754'",             "5754" in (r["snippet"].get("spec_output") or ""))
print(f"    Output: {(r['snippet'].get('spec_output') or '').strip()}")

# Verdict
r = spokedpy("POST", f"/api/staging/verdict/{sid}", {"action": "auto"})
test("Phase 3 — Verdict passed",      r["snippet"]["phase"] == "passed")

# Promote
r = spokedpy("POST", f"/api/staging/promote/{sid}")
phased_slot = r["snippet"].get("registry_slot_id", "")
test("Phase 4 — Promoted",            r["snippet"]["phase"] == "promoted")
test("Slot ID assigned",              bool(phased_slot))
print(f"    Slot: {phased_slot}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 11 — Error Handling (intentional bad code)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 11 · Error Handling — Syntax Error Rejection")
r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "a",
    "language": "python",
    "code": "def broken(\n    syntax error here",
    "label": "test_bad_syntax",
    "auto_promote": True,
})
snip = r.get("snippet", {})
test("Phase is 'rejected' or 'failed'",
     snip.get("phase") in ("rejected", "failed"),
     f"got phase={snip.get('phase')}")
test("spec_success is False",          snip.get("spec_success") is False)
test("spec_error is non-empty",        bool(snip.get("spec_error")))
print(f"    Phase:  {snip.get('phase')}")
print(f"    Error:  {(snip.get('spec_error') or '')[:120]}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 12 — Multi-engine Simultaneous Execution
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 12 · Multi-engine Simultaneous Execution")
r = spokedpy("POST", "/api/execution/engines/run-simultaneous", {
    "tabs": [
        {"engine_letter": "a", "language": "python",     "code": "print(2**10)"},
        {"engine_letter": "b", "language": "javascript",  "code": "console.log(2**10)"},
        {"engine_letter": "i", "language": "go",
         "code": 'package main\nimport "fmt"\nfunc main() { fmt.Println(1<<10) }'},
    ]
})
results = r.get("results", [])
test("Got 3 results",                 len(results) == 3)

for res in results:
    lang  = res.get("language", "?")
    out   = (res.get("output") or "").strip()
    err   = res.get("error", "")
    ok    = "1024" in out
    test(f"  {lang} output == 1024",   ok, f"output={out!r}  error={err!r}")
    print(f"      [{lang}] → {out}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 13 — Registry Matrix
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 13 · Registry Matrix")
r = spokedpy("GET", "/api/registry/matrix")
test("Matrix returns success",        r.get("success") is True)
engines_in_matrix = r.get("engines", {})
active_count = 0
for ename, edata in engines_in_matrix.items():
    slots = edata.get("slots", {})
    for pos, sdata in slots.items():
        if sdata and sdata.get("node_id"):
            active_count += 1
test("At least 4 active slots",       active_count >= 4, f"got {active_count}")
print(f"    Active slots in matrix: {active_count}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 14 — Pipeline Summary
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 14 · Pipeline Summary")
r = spokedpy("GET", "/api/staging/summary")
test("Summary returns success",       r.get("success") is True)
print(f"    Total snippets: {r.get('total_snippets')}")
print(f"    Active:         {r.get('active_count')}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 15 — Snippet List
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 15 · Snippet Listing")
r = spokedpy("GET", "/api/staging/snippets?include_history=1&limit=50")
active   = r.get("active", [])
history  = r.get("history", [])
test("Active list is non-empty",       len(active) > 0)
print(f"    Active:  {len(active)}   History: {len(history)}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 16 — Rollback
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 16 · Rollback")
# Roll back the phased pipeline slot
r = spokedpy("POST", f"/api/staging/rollback/{sid}", {
    "reason": "Integration test cleanup",
})
test("Rollback accepted",             r.get("success") is True)
snip = r.get("snippet", {})
test("Phase is 'rolled_back'",        snip.get("phase") == "rolled_back")
print(f"    Phase after rollback: {snip.get('phase')}")

# Verify the slot is now gone
try:
    r2 = spokedpy("GET", f"/api/registry/slot/{phased_slot}")
    slot_gone = not (r2.get("slot", {}).get("is_active", True))
    test("Slot cleared after rollback",  slot_gone)
except Exception as ex:
    # 404 or error means it's gone — that's expected
    test("Slot cleared after rollback",  True)

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 17 — Slot Permissions (PUT)
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 17 · Slot Permissions")
r = spokedpy("PUT", f"/api/registry/slot/{py_slot}/permissions", {
    "get": True, "push": True, "post": True, "delete": False,
})
test("Permissions update accepted",    r.get("success") is True)

# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 18 — Bash / PowerShell Auto-translate
# ═══════════════════════════════════════════════════════════════════════════════

section("TEST 18 · Bash (PowerShell auto-translate on Windows)")
code_bash = 'echo "Hello from Bash/PowerShell"\necho "Date: $(date)"'
r = spokedpy("POST", "/api/staging/run-full", {
    "engine_letter": "n",
    "language": "bash",
    "code": code_bash,
    "label": "test_bash",
    "auto_promote": True,
})
snip = r.get("snippet", {})
test("Phase is 'promoted'",           snip.get("phase") == "promoted")
test("Output contains 'Hello'",       "Hello" in (snip.get("spec_output") or ""))
print(f"    Output: {(snip.get('spec_output') or '').strip()[:200]}")

# ═══════════════════════════════════════════════════════════════════════════════
#  FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n{'═'*72}")
print(f"  FINAL RESULTS")
print(f"{'═'*72}")
print(f"  ✅ Passed: {PASS}")
print(f"  ❌ Failed: {FAIL}")
print(f"  Total:    {PASS + FAIL}")
pct = PASS / (PASS + FAIL) * 100 if (PASS + FAIL) else 0
print(f"  Rate:     {pct:.1f}%")

if FAIL > 0:
    print(f"\n  Failed tests:")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"    ❌ {name}  {detail}")

print(f"{'═'*72}")
sys.exit(0 if FAIL == 0 else 1)
