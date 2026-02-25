# Demo Import Files — Live Execution & Engine Matrix
These Python files are designed to be imported through the SpokedPy UI
to test the **Live Execution Panel** in both **Ledger** and **Registry** modes.

---

## How to Use

1. **Start the server** — `cd web_interface && python app.py`
2. **Open the UI** — `http://localhost:5002`
3. **Import a demo file:**
   - Click the import / file button in the toolbar
   - Select one of the `.py` files from this folder
   - Confirm the import — nodes will appear on the canvas
4. **Open the Live Execution panel** — click the ⚡ button
5. **Click Refresh** to load nodes from the ledger
6. **Test Ledger mode** (default):
   - Select a node → click **Run**
   - Or click **Run All** to execute everything in order
   - Check the **Variables** panel for shared namespace state
   - Check **Execution History** for timing per node
7. **Switch to Registry mode** — flip the toggle from "Ledger" to "Registry"
   - The **Engine Matrix** grid appears (17 rows × 8 columns)
   - **Run** or **Run All** — nodes commit to registry slots first
   - Watch the grid cells light up:
     - 🔵 **Cyan dot** = committed (idle)
     - 🔵 **Pulsing cyan** = executing
     - 🟢 **Green flash** = success
     - 🔴 **Red flash** = error
     - 🟠 **Amber pulse** = hot-swap pending (code changed since last commit)

---

## Files

| File | Nodes | Purpose |
|------|-------|---------|
| `01_hello_world.py` | 2 | Simplest test — `greet` and `count_to` |
| `02_data_pipeline.py` | 4 | Chained data flow — generate → filter → stats → summarize |
| `03_algorithms.py` | 4 | Classic algorithms — fibonacci, factorial, prime check, Collatz |
| `04_grid_ops.py` | 5 | 2D grid operations — create, transpose, sums, max, flatten |
| `05_registry_stress_test.py` | 8 | Fills an entire engine row (a1–a8) — max-slot stress test |

**Total: 23 importable functions across 5 files**

---

## What to Look For

### Ledger Mode
- Output appears in the terminal at the bottom of the panel
- Variables accumulate across runs (REPL-style shared namespace)
- "Run All" shows a summary at the end (passed/failed/time)

### Registry Mode
- Nodes are **committed** to the Engine Matrix before execution
- Row `a` (Python) populates with blue dots as nodes commit
- Each dot pulses during execution, then flashes green/red
- The stats line updates: "N committed · 0 pending · N total"
- After modifying a node's code, uncommitted changes show as amber (hot-swap pending)

### Stress Test (File 05)
- All 8 functions fill slots a1–a8 (the maximum per engine row)
- "Run All" produces a cascade of green flashes across the entire row
- The last function (`slot_hotel`) references the others by name
