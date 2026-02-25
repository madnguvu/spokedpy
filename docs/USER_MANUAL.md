# SpokedPy User Manual

## Visual Python Designer — Getting Started Guide

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [The Visual Canvas](#4-the-visual-canvas)
5. [Working with Nodes](#5-working-with-nodes)
6. [Creating Connections](#6-creating-connections)
7. [The Properties Panel](#7-the-properties-panel)
8. [AI Assistant](#8-ai-assistant)
9. [Pattern Search & Refactoring](#9-pattern-search--refactoring)
10. [Code Generation](#10-code-generation)
11. [Execution & Debugging](#11-execution--debugging)
12. [Visual Paradigms](#12-visual-paradigms)
13. [Importing Code](#13-importing-code)
14. [Keyboard Shortcuts](#14-keyboard-shortcuts)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Introduction

### What is SpokedPy?

SpokedPy (Visual Python Designer) is a visual programming platform that allows you to create Python applications by connecting visual nodes on a canvas. Instead of writing code line by line, you:

1. **Drag nodes** from the palette onto the canvas
2. **Connect them** to define data flow
3. **Configure parameters** in the properties panel
4. **Generate code** or execute directly

### Who is SpokedPy for?

- **Developers** seeking rapid prototyping
- **Data Scientists** building data pipelines
- **Students** learning programming concepts
- **Educators** teaching visual programming
- **Business Analysts** creating automation workflows

---

## 2. Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Edge)

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd SpokedPy

# 2. Create a virtual environment (recommended)
python -m venv venv

# 3. Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the web interface
cd web_interface
python app.py
```

### Accessing the Application

Once started, open your browser and navigate to:

```
http://localhost:5002
```

You should see the SpokedPy visual editor interface.

---

## 3. Quick Start

### Your First Visual Program

Let's create a simple "Hello World" program:

**Step 1: Open the Node Palette**
- Click the palette icon in the left toolbar
- Or use the keyboard shortcut

**Step 2: Add a Variable Node**
- Find "Variable" under "Basic" category
- Drag it onto the canvas
- Click to select it

**Step 3: Configure the Variable**
- In the Properties Panel (right side):
  - Set `name` to `message`
  - Set `value` to `"Hello, World!"`

**Step 4: Add a Function Node**
- Drag a "Function" node onto the canvas
- Position it to the right of the variable

**Step 5: Configure as Print**
- Select the function node
- Set `name` to `print`

**Step 6: Connect the Nodes**
- Click and drag from the variable's output port
- Drop on the function's input port

**Step 7: Execute**
- Click the "Run" button in the toolbar
- See "Hello, World!" in the output panel

Congratulations! You've created your first visual program.

---

## 4. The Visual Canvas

### Canvas Overview

The canvas is your main workspace where you design visual programs.

```
┌────────────────────────────────────────────────────────┐
│ Toolbar                                                │
├──────┬─────────────────────────────────────────┬───────┤
│      │                                         │       │
│ Node │           Visual Canvas                 │ Props │
│Palette│                                        │ Panel │
│      │     [Node A] ───────► [Node B]         │       │
│      │                                         │       │
├──────┴─────────────────────────────────────────┴───────┤
│ Status Bar                                             │
└────────────────────────────────────────────────────────┘
```

### Navigation Controls

| Action | Mouse | Keyboard |
|--------|-------|----------|
| Pan | Middle-click drag | Hold Space + drag |
| Zoom In | Scroll up | Ctrl + Plus |
| Zoom Out | Scroll down | Ctrl + Minus |
| Fit to View | — | Ctrl + 0 |
| Reset Zoom | — | Ctrl + 1 |

### Canvas Actions

| Action | How To |
|--------|--------|
| Select Node | Click on node |
| Multi-Select | Ctrl + Click or drag rectangle |
| Move Node | Drag selected node(s) |
| Delete | Select + Delete key |
| Duplicate | Ctrl + D |
| Undo | Ctrl + Z |
| Redo | Ctrl + Y |

---

## 5. Working with Nodes

### Node Anatomy

```
    ┌─────────────────────┐
    │  📦 Node Title      │
    │─────────────────────│
○──│ input1              │──○
○──│ input2              │
    │         output ────│──○
    │─────────────────────│
    │ [Code Preview]      │
    └─────────────────────┘
```

- **Title**: Node name/type
- **Input Ports** (left): Receive data from other nodes
- **Output Ports** (right): Send data to other nodes
- **Code Preview**: Shows source code if enabled

### Adding Nodes

**Method 1: Node Palette**
1. Click palette icon or press `P`
2. Browse categories or search
3. Drag node to canvas

**Method 2: Right-Click Menu**
1. Right-click on canvas
2. Select "Add Node"
3. Choose from menu

**Method 3: Quick Add**
1. Double-click on canvas
2. Type node name
3. Press Enter

### Node Categories

| Category | Examples |
|----------|----------|
| **Basic** | Variable, Constant, Function, Return |
| **Control Flow** | If, For Loop, While Loop, Break |
| **Data Types** | String, Number, List, Dict, Tuple |
| **OOP** | Class, Method, Property, Inheritance |
| **Functional** | Lambda, Map, Filter, Reduce |
| **Async** | Async Function, Await, Parallel |
| **I/O** | File Read, File Write, HTTP Request |
| **Error Handling** | Try/Except, Raise |

---

## 6. Creating Connections

### Basic Connection

1. **Start**: Click and hold on an output port (right side)
2. **Drag**: Pull the connection line
3. **Drop**: Release on an input port (left side)

### Connection Rules

- ✅ Output port → Input port (valid)
- ❌ Input port → Input port (invalid)
- ❌ Output port → Output port (invalid)
- ⚠️ Type mismatch shows warning

### Connection Tips

| Tip | Description |
|-----|-------------|
| **Snap to port** | Connection snaps when near valid port |
| **Cancel** | Press Escape or release on empty canvas |
| **Delete** | Click connection, press Delete |
| **Reroute** | Drag connection to different port |

### Data Flow Direction

Data always flows **left to right**:

```
[Variable] ──► [Transform] ──► [Output]
   value         process        display
```

---

## 7. The Properties Panel

### Accessing Properties

1. Select a node on canvas
2. Properties Panel appears on right
3. Edit values and press Enter or Tab

### Properties Tabs

#### Parameters Tab
Edit the node's functional parameters:

| Field | Description |
|-------|-------------|
| Name | Identifier for the node |
| Value | Default or constant value |
| Type | Data type (str, int, etc.) |
| Description | Documentation |

#### Ports Tab
Manage input and output ports:

| Action | How To |
|--------|--------|
| Add Port | Click "+ Add Input" or "+ Add Output" |
| Edit Port | Change name, type, required |
| Delete Port | Click trash icon |
| Reorder | Drag to reposition |

#### Source Tab
View and edit the node's source code:

```python
def my_function(input1, input2):
    result = input1 + input2
    return result
```

### Saving Changes

- Changes save automatically when you:
  - Press Enter
  - Tab to next field
  - Click outside the panel
  - Select another node

---

## 8. AI Assistant

### Opening the AI Panel

- Click the **"AI Assistant"** tab on the right edge
- Or press `Ctrl + Shift + A`

### Configuring AI

1. Click the **⚙️ Settings** button
2. Configure your API:

| Setting | Description |
|---------|-------------|
| **Endpoint** | API URL (default: OpenAI) |
| **API Key** | Your API key (stored locally) |
| **Model** | GPT-4o, GPT-3.5, Claude, etc. |
| **Temperature** | Creativity level (0-2) |

3. Click **Save Settings**

### Using the AI Assistant

**Ask questions:**
```
"What nodes are on my canvas?"
"How do I create a file reader?"
"Explain how the map node works"
```

**Generate nodes:**
```
"Create a data processing pipeline that reads a CSV file,
filters rows where age > 18, and saves to JSON"
```

**The AI will respond with:**
- Explanations in natural language
- Generated code blocks
- **Inject-able node definitions**

### Injecting AI-Generated Nodes

When AI generates nodes:

1. A code block appears with `📦 Generated Nodes (X)`
2. Click **"Add X nodes to Canvas"** button
3. Nodes appear on your canvas automatically

### Quick Actions

Pre-built prompts for common tasks:

| Button | Action |
|--------|--------|
| 📊 Data Pipeline | Generate ETL workflow |
| 🔍 Analyze Canvas | Describe current nodes |
| 📁 JSON Processor | Create JSON handler |

---

## 9. Pattern Search & Refactoring

### Opening Pattern Search

- Click **🔍 Search** button in toolbar
- Or press `Ctrl + F`

### Searching Patterns

1. Enter a pattern in the search box:
   ```
   def $FUNC($ARGS)
   ```

2. Click **Search**

3. Results show matching nodes

### Pattern Syntax

| Pattern | Matches |
|---------|---------|
| `def` | All function definitions |
| `print($MSG)` | All print calls |
| `for $VAR in $ITER` | All for loops |
| `$VAR = $VALUE` | All assignments |
| `if $COND: $$$BODY` | All if statements |

**Wildcards:**
- `$VAR` - Single expression
- `$$$VAR` - Multiple statements

### Tagging Results

After searching:

1. ☑️ Check **"Tag Search Results"**
2. Matched nodes get **green outlines**
3. Match counts appear as badges

**To clear tags:**
- Uncheck the checkbox, or
- Click **"Clear All Tags"**

### Refactoring

1. Switch to **Refactor** tab
2. Enter find pattern:
   ```
   print($MSG)
   ```
3. Enter replacement:
   ```
   logger.info($MSG)
   ```
4. Click **Preview**
5. Review changes
6. Click **Apply Refactor**

---

## 10. Code Generation

### Generating Python Code

1. Design your visual program
2. Click **Export** → **Python Code**
3. Configure options:

| Option | Description |
|--------|-------------|
| Format Code | Apply PEP 8 formatting |
| Add Type Hints | Include type annotations |
| Add Docstrings | Generate documentation |
| Optimize | Remove redundant code |

4. Click **Generate**
5. Copy or save the code

### Example Output

Visual program:
```
[Variable: x=5] ──► [Function: square] ──► [Function: print]
```

Generated Python:
```python
"""Auto-generated by SpokedPy"""

def square(value: int) -> int:
    """Calculate the square of a value."""
    return value ** 2

x: int = 5
result = square(x)
print(result)
```

---

## 11. Execution & Debugging

### Running Your Program

**Quick Run:**
- Click **▶️ Run** button
- Or press `F5`

**Output appears in:**
- Output Panel (bottom)
- Console tab

### Debug Mode

1. Click **🐛 Debug** button
2. Set breakpoints:
   - Click the dot beside a node
   - Or right-click → "Toggle Breakpoint"

3. Run in debug mode

### Debug Controls

| Button | Action | Shortcut |
|--------|--------|----------|
| ▶️ Continue | Run to next breakpoint | F5 |
| ⏭️ Step Over | Execute current node | F10 |
| ⏬ Step Into | Enter function | F11 |
| ⏹️ Stop | End execution | Shift+F5 |

### Variable Inspection

During debugging:

1. Hover over node to see values
2. Check **Variables** panel for all values
3. Add **Watch Expressions** for specific variables

---

## 12. Visual Paradigms

### Switching Paradigms

1. Click paradigm selector in toolbar
2. Choose:
   - **Node-Based**: Flow chart style
   - **Block-Based**: Nested blocks (like Scratch)
   - **Diagram-Based**: UML class diagrams
   - **Timeline-Based**: Sequential/async view

### Paradigm Comparison

| Paradigm | Best For |
|----------|----------|
| Node-Based | Data flow, transformations |
| Block-Based | Control logic, beginners |
| Diagram-Based | OOP design, architecture |
| Timeline-Based | Async operations, events |

### Loading Demo Applications

1. Click **Demos** in menu
2. Select a demo:
   - Data Processing Pipeline (Node-Based)
   - Interactive Game Logic (Block-Based)
   - Object-Oriented Design (Diagram-Based)
   - Async Event Processing (Timeline-Based)

---

## 13. Importing Code

### Import Existing Python

1. Click **Import** → **Python File**
2. Select your `.py` file
3. SpokedPy parses and creates nodes

### Repository Analysis

1. Click **Analyze** → **Repository**
2. Upload multiple files
3. SpokedPy analyzes:
   - Functions
   - Classes
   - Dependencies
   - Imports

4. Click to import functions as nodes

### Generate from Library

1. Click **Library** → **Generate Nodes**
2. Enter module name (e.g., `json`, `os`)
3. SpokedPy creates nodes for all functions

---

## 14. Keyboard Shortcuts

### General

| Shortcut | Action |
|----------|--------|
| Ctrl + N | New canvas |
| Ctrl + O | Open file |
| Ctrl + S | Save |
| Ctrl + Z | Undo |
| Ctrl + Y | Redo |
| Ctrl + A | Select all |
| Delete | Delete selected |

### Canvas Navigation

| Shortcut | Action |
|----------|--------|
| Space + Drag | Pan canvas |
| Ctrl + Plus | Zoom in |
| Ctrl + Minus | Zoom out |
| Ctrl + 0 | Fit to view |
| Ctrl + 1 | Reset zoom (100%) |

### Nodes

| Shortcut | Action |
|----------|--------|
| P | Open palette |
| Ctrl + D | Duplicate selected |
| Ctrl + G | Group selected |
| Ctrl + Shift + G | Ungroup |

### Execution

| Shortcut | Action |
|----------|--------|
| F5 | Run / Continue |
| F10 | Step over |
| F11 | Step into |
| Shift + F5 | Stop execution |
| F9 | Toggle breakpoint |

### Panels

| Shortcut | Action |
|----------|--------|
| Ctrl + F | Open search |
| Ctrl + Shift + A | Toggle AI panel |
| Ctrl + P | Toggle properties |

---

## 15. Troubleshooting

### Common Issues

#### "Cannot connect to server"

**Solution:**
1. Ensure `app.py` is running
2. Check the terminal for errors
3. Verify port 5002 is not in use
4. Try restarting the server

#### "Node not appearing on canvas"

**Solution:**
1. Check if node is outside visible area
2. Press Ctrl+0 to fit to view
3. Look in the nodes layer

#### "Connections not working"

**Solution:**
1. Verify port types are compatible
2. Check for existing connections
3. Ensure nodes are not in error state

#### "AI Assistant not responding"

**Solution:**
1. Verify API key is correct
2. Check endpoint URL
3. Ensure you have API credits
4. Check network connection

#### "Search returns no results"

**Solution:**
1. Verify pattern syntax
2. Check that nodes have source code
3. Try a simpler pattern first
4. Ensure nodes are loaded on canvas

### Getting Help

- **Documentation**: Check `SYSTEM_OVERVIEW.md`
- **Feature List**: See `FEATURE_INVENTORY.md`
- **API Reference**: See docstrings in source code

### Reporting Issues

When reporting bugs, include:

1. Steps to reproduce
2. Expected behavior
3. Actual behavior
4. Browser and OS information
5. Console error messages

---

## Appendix A: Node Reference

See `FEATURE_INVENTORY.md` for complete node type documentation.

## Appendix B: API Reference

See `web_interface/app.py` docstrings for API endpoint documentation.

## Appendix C: Configuration

### Server Configuration

Edit `web_interface/app.py`:

```python
# Change port
socketio.run(app, debug=True, host='0.0.0.0', port=5002)

# Production mode
socketio.run(app, debug=False, host='0.0.0.0', port=80)
```

### Canvas Settings

Edit in browser localStorage:
- `SpokedPy_canvas_settings` - Canvas preferences
- `SpokedPy_ai_settings` - AI configuration

---

*SpokedPy User Manual — Version 1.0*
*Last Updated: February 2026*
