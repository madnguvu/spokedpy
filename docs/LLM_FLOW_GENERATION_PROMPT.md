# SpokedPy Visual Flow Generation Prompt

Use this prompt with any LLM (ChatGPT, Claude, etc.) to generate importable visual flows for SpokedPy.

---

##  THE PROMPT (Copy everything below this line)

---

I need you to create a visual programming flow for SpokedPy - a visual Python designer. Generate a JSON object that I can directly import into the canvas.

## OUTPUT FORMAT

Return ONLY valid JSON in this exact structure:

```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "<node_type>",
      "position": [x, y],
      "parameters": {
        "name": "Human readable name",
        "source_code": "# Python code for this node",
        "<other_properties>": "..."
      },
      "metadata": {
        "description": "What this node does"
      }
    }
  ],
  "connections": [
    {
      "id": "conn_1",
      "source_node_id": "node_1",
      "source_port": "output_port_name",
      "target_node_id": "node_2",
      "target_port": "input_port_name"
    }
  ]
}
```

## LAYOUT RULES

- Start nodes at position [100, 100]
- Space nodes horizontally by 250 pixels
- Space nodes vertically by 150 pixels
- Flow generally left-to-right, top-to-bottom
- Group related nodes vertically

## AVAILABLE NODE TYPES

### Functions Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `function` | Function | parameters | result | Define a reusable function |
| `async_function` | Async Function | parameters | result | Async function definition |
| `lambda` | Lambda | parameters | result | Anonymous inline function |
| `generator` | Generator | parameters | yields | Generator function with yield |
| `decorator` | Decorator | function | decorated | Function decorator |
| `method` | Method | self, parameters | result | Class method |

### Variables Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `variable` | Variable | value | output | Mutable variable |
| `constant` | Constant | - | value | Immutable constant value |
| `global` | Global | - | value | Global variable access |
| `attribute` | Attribute | object | value | Object attribute access |
| `variable_set` | Set Variable | value | - | Assign value to variable |
| `variable_get` | Get Variable | - | value | Read variable value |

### Control Flow Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `if` | If/Else | condition | true_branch, false_branch | Conditional branching |
| `if_statement` | If | condition | true_branch, false_branch | If statement |
| `while` | While Loop | condition, body | output | While loop |
| `while_loop` | While | condition, body | output | While loop block |
| `for` | For Loop | iterable, body | output | For each iteration |
| `for_loop` | For | iterable, body | output | For loop block |
| `break` | Break | trigger | - | Exit loop |
| `continue` | Continue | trigger | - | Skip to next iteration |
| `pass` | Pass | trigger | output | No-op placeholder |
| `return` | Return | value | - | Return from function |
| `yield` | Yield | value | next | Yield value from generator |
| `yield_from` | Yield From | iterable | next | Delegate to sub-generator |
| `sequence` | Sequence | inputs | output | Sequential execution |
| `delay` | Delay | input, duration | output | Wait/delay execution |

### Exception Handling Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `try_except` | Try/Except | try_block | success, exception | Exception handling |
| `try_finally` | Try/Finally | try_block, finally_block | output | Cleanup with finally |
| `raise` | Raise | exception | - | Raise an exception |
| `assert` | Assert | condition, message | output | Assert condition |

### Classes & OOP Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `class` | Class | bases | class_type | Define a class |
| `abstract_class` | Abstract Class | bases | class_type | Abstract class definition |
| `interface` | Interface | - | interface | Interface definition |
| `init_method` | Constructor | self, args | - | __init__ method |
| `property` | Property | getter, setter | property | Property accessor |
| `inheritance` | Inheritance | child, parent | derived_class | Class inheritance |
| `super_call` | Super Call | args | result | Call parent method |

### Data Structures Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `list` | List | items | list | Create a list |
| `tuple` | Tuple | items | tuple | Create a tuple |
| `dict` | Dictionary | keys, values | dict | Create a dictionary |
| `set` | Set | items | set | Create a set |
| `frozenset` | Frozenset | items | frozenset | Create immutable set |
| `namedtuple` | Named Tuple | values | namedtuple | Named tuple instance |
| `dataclass` | Data Class | field_values | instance | Dataclass instance |
| `enum` | Enum | - | enum_type | Enumeration type |

### Comprehensions Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `list_comprehension` | List Comp | iterable, condition | list | [x for x in ...] |
| `dict_comprehension` | Dict Comp | iterable, condition | dict | {k:v for ...} |
| `set_comprehension` | Set Comp | iterable, condition | set | {x for x in ...} |
| `generator_expression` | Gen Expr | iterable, condition | generator | (x for x in ...) |

### Context Managers Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `with_statement` | With | context_manager | resource, body_output | with ... as ... |
| `context_manager` | Context Mgr | enter_logic, exit_logic | context_manager | Custom context manager |

### Async/Await Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `async_function` | Async Func | parameters | result | async def function |
| `await` | Await | coroutine | result | await expression |
| `async_for` | Async For | async_iterable | output | async for loop |
| `async_with` | Async With | async_context_manager | resource, body_output | async with |
| `task` | Task | coroutine | task | Create async task |
| `gather` | Gather | coroutines | results | Await multiple coroutines |

### I/O Operations Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `file_read` | Read File | filename | content | Read file contents |
| `file_write` | Write File | filename, content | success | Write to file |
| `print` | Print | value | - | Print to output |
| `print_statement` | Print | value | - | Print statement |
| `input` | Input | prompt | value | Read user input |
| `input_statement` | Input | prompt | value | Input statement |
| `http_request` | HTTP Request | url, method, data | response | Make HTTP call |

### Operators Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `arithmetic` | Arithmetic | left, right | result | +, -, *, /, %, ** |
| `comparison` | Comparison | left, right | result | ==, !=, <, >, <=, >= |
| `logical` | Logical | left, right | result | and, or, not |
| `bitwise` | Bitwise | left, right | result | &, \|, ^, ~, <<, >> |
| `membership` | Membership | item, container | result | in, not in |
| `identity` | Identity | left, right | result | is, is not |
| `ternary` | Ternary | condition, true_val, false_val | result | x if cond else y |
| `walrus` | Walrus | expression | value | := operator |

### String Operations Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `string_format` | Format | template, values | formatted | f-string or .format() |
| `string_join` | Join | separator, items | result | "sep".join(list) |
| `string_split` | Split | string, separator | parts | str.split(sep) |
| `regex` | Regex | pattern, string | matches | Regular expression |

### Type Operations Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `type_check` | Type Check | value, type | result | isinstance() check |
| `type_cast` | Type Cast | value | result | int(), str(), etc. |
| `type_hint` | Type Hint | - | type | Type annotation |

### Builtin Functions Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `len` | Length | sequence | length | len() function |
| `range` | Range | start, stop, step | range | range() iterator |
| `enumerate` | Enumerate | iterable | enumerated | enumerate() with index |
| `zip` | Zip | iterables | zipped | zip() multiple iterables |
| `map` | Map | function, iterable | mapped | map() transform |
| `filter` | Filter | predicate, iterable | filtered | filter() elements |
| `reduce` | Reduce | function, iterable, initial | result | functools.reduce() |
| `sorted` | Sorted | iterable | sorted | sorted() list |
| `reversed` | Reversed | sequence | reversed | reversed() iterator |
| `any_all` | Any/All | iterable | result | any() or all() |
| `min_max` | Min/Max | items | result | min() or max() |
| `sum` | Sum | iterable | total | sum() total |
| `abs` | Abs | number | result | abs() value |
| `round` | Round | number, digits | rounded | round() number |

### Concurrency Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `parallel` | Parallel | tasks | results | Run tasks in parallel |
| `timer` | Timer | interval | trigger | Periodic timer |
| `event` | Event | - | signal | Event trigger |
| `process` | Process | code | output | Subprocess |

### Import/Module Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `import` | Import | - | module | import module |
| `from_import` | From Import | - | imported_items | from x import y |
| `module` | Module | - | module | Module reference |
| `package` | Package | - | package | Package reference |

### Custom Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `custom` | Custom | configurable | configurable | User-defined node |
| `library_function` | Library Func | args | result | External library call |
| `external_call` | External Call | args | result | External system call |

### Documentation Category
| Type | Name | Inputs | Outputs | Description |
|------|------|--------|---------|-------------|
| `comment` | Comment | - | - | Code comment |
| `docstring` | Docstring | - | - | Documentation string |
| `todo` | TODO | - | - | TODO marker |

## NODE PARAMETERS

Each node can have these standard parameters:

```json
{
  "name": "Display name for the node",
  "source_code": "# Actual Python code this node represents",
  "value": "For constants/variables",
  "operator": "+|-|*|/|==|!=|<|>|and|or",
  "condition": "Boolean expression",
  "filename": "For file operations",
  "url": "For HTTP operations",
  "method": "GET|POST|PUT|DELETE",
  "exception_types": ["ValueError", "TypeError"],
  "class_name": "ClassName",
  "function_name": "function_name",
  "variable_name": "var_name",
  "expression": "Python expression",
  "transform": "Expression for map/filter",
  "module_name": "module.to.import",
  "import_items": ["item1", "item2"]
}
```

## CONNECTION RULES

1. Connect output ports to input ports only
2. Use exact port names from the node definitions above
3. Each input port can have only one incoming connection
4. Output ports can have multiple outgoing connections

## EXAMPLES

### Example 1: Simple Calculator Function

```json
{
  "nodes": [
    {
      "id": "func_1",
      "type": "function",
      "position": [100, 100],
      "parameters": {
        "name": "add_numbers",
        "source_code": "def add_numbers(a, b):\n    return a + b"
      },
      "metadata": {"description": "Add two numbers"}
    },
    {
      "id": "var_a",
      "type": "variable",
      "position": [100, 250],
      "parameters": {"name": "a", "value": "10"},
      "metadata": {}
    },
    {
      "id": "var_b",
      "type": "variable",
      "position": [100, 400],
      "parameters": {"name": "b", "value": "20"},
      "metadata": {}
    },
    {
      "id": "add_op",
      "type": "arithmetic",
      "position": [350, 325],
      "parameters": {"name": "Add", "operator": "+"},
      "metadata": {}
    },
    {
      "id": "result",
      "type": "print",
      "position": [600, 325],
      "parameters": {"name": "Print Result"},
      "metadata": {}
    }
  ],
  "connections": [
    {"id": "c1", "source_node_id": "var_a", "source_port": "output", "target_node_id": "add_op", "target_port": "left"},
    {"id": "c2", "source_node_id": "var_b", "source_port": "output", "target_node_id": "add_op", "target_port": "right"},
    {"id": "c3", "source_node_id": "add_op", "source_port": "result", "target_node_id": "result", "target_port": "value"}
  ]
}
```

### Example 2: File Processing with Error Handling

```json
{
  "nodes": [
    {
      "id": "file_input",
      "type": "constant",
      "position": [100, 100],
      "parameters": {"name": "Filename", "value": "data.txt"},
      "metadata": {}
    },
    {
      "id": "try_block",
      "type": "try_except",
      "position": [350, 100],
      "parameters": {"name": "Try Read File", "exception_types": ["FileNotFoundError", "IOError"]},
      "metadata": {}
    },
    {
      "id": "read_file",
      "type": "file_read",
      "position": [350, 250],
      "parameters": {"name": "Read File"},
      "metadata": {}
    },
    {
      "id": "process",
      "type": "function",
      "position": [600, 100],
      "parameters": {"name": "Process Data", "source_code": "def process(data):\n    return data.upper()"},
      "metadata": {}
    },
    {
      "id": "error_handler",
      "type": "print",
      "position": [600, 250],
      "parameters": {"name": "Error Handler", "source_code": "print('Error reading file')"},
      "metadata": {}
    }
  ],
  "connections": [
    {"id": "c1", "source_node_id": "file_input", "source_port": "value", "target_node_id": "read_file", "target_port": "filename"},
    {"id": "c2", "source_node_id": "read_file", "source_port": "content", "target_node_id": "try_block", "target_port": "try_block"},
    {"id": "c3", "source_node_id": "try_block", "source_port": "success", "target_node_id": "process", "target_port": "parameters"},
    {"id": "c4", "source_node_id": "try_block", "source_port": "exception", "target_node_id": "error_handler", "target_port": "value"}
  ]
}
```

### Example 3: Async API Call

```json
{
  "nodes": [
    {
      "id": "async_main",
      "type": "async_function",
      "position": [100, 100],
      "parameters": {"name": "fetch_data", "source_code": "async def fetch_data():"},
      "metadata": {}
    },
    {
      "id": "api_url",
      "type": "constant",
      "position": [100, 250],
      "parameters": {"name": "API URL", "value": "https://api.example.com/data"},
      "metadata": {}
    },
    {
      "id": "http_call",
      "type": "http_request",
      "position": [350, 175],
      "parameters": {"name": "GET Request", "method": "GET"},
      "metadata": {}
    },
    {
      "id": "await_response",
      "type": "await",
      "position": [600, 175],
      "parameters": {"name": "Await Response"},
      "metadata": {}
    },
    {
      "id": "print_result",
      "type": "print",
      "position": [850, 175],
      "parameters": {"name": "Print Data"},
      "metadata": {}
    }
  ],
  "connections": [
    {"id": "c1", "source_node_id": "api_url", "source_port": "value", "target_node_id": "http_call", "target_port": "url"},
    {"id": "c2", "source_node_id": "http_call", "source_port": "response", "target_node_id": "await_response", "target_port": "coroutine"},
    {"id": "c3", "source_node_id": "await_response", "source_port": "result", "target_node_id": "print_result", "target_port": "value"}
  ]
}
```

---

## MY REQUEST

Now please create a flow for the following:

**[DESCRIBE WHAT YOU WANT HERE]**

Requirements:
- Use only the node types listed above
- Return ONLY the JSON, no explanation
- Make sure all connections use valid port names
- Position nodes logically in a readable layout
- Include meaningful names and descriptions

---

# END OF PROMPT

---

## 📋 How to Use This Prompt

1. **Copy** everything between "THE PROMPT" and "END OF PROMPT"
2. **Paste** into your LLM (ChatGPT, Claude, etc.)
3. **Replace** `[DESCRIBE WHAT YOU WANT HERE]` with your requirements
4. **Copy** the JSON response
5. **Import** into SpokedPy:
   - Click **File → Import Canvas** (or press `Ctrl+I`)
   - Paste the JSON
   - Click **Import**

## 💡 Tips for Better Results

1. **Be specific** about what you want the flow to do
2. **Mention data types** if relevant (strings, numbers, lists, etc.)
3. **Describe the flow** step by step if it's complex
4. **Specify error handling** if you need it
5. **Mention if you need async** functionality

## 🔧 Example Requests to Add

Replace `[DESCRIBE WHAT YOU WANT HERE]` with requests like:

- "A flow that reads a CSV file, filters rows where 'status' is 'active', and writes the result to a new file"
- "An async flow that fetches data from 3 different APIs in parallel and combines the results"
- "A class hierarchy with Person as base class and Employee and Customer as subclasses"
- "A web scraper that retries 3 times on failure with exponential backoff"
- "A data pipeline that reads JSON, transforms each record, and saves to database"

