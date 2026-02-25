
<img width="355" height="120" alt="image" src="https://github.com/user-attachments/assets/cf427630-b2c9-4b45-a2ee-be02fbc29772" />


<img width="1911" height="966" alt="image" src="https://github.com/user-attachments/assets/d9f3d665-f1b4-4284-b049-53560178dc75" />



Full 40+ Pages of details here:  https://github.com/madnguvu/spokedpy/blob/main/docs/TECHNICAL_SPECIFICATION.md


## Summary

SpokedPy is a visual programming platform that treats source code as a **translatable, executable, auditable data structure**. Its three-pillar architecture — the UIR for language neutrality, the Session Ledger for event sourcing, and the Node Registry for register-file execution — represents a fundamentally new approach to how developers interact with code.

The system is not a prototype. It is 73,000+ lines of tested, modular, production-oriented software with a clear path to enterprise deployment, academic publication, and commercial viability.

---

*SpokedPy — Code is data. Data is visual. Visual is executable.*

Download Zip file.  Extract.  Use Pip for installing dependencies.  From terminal, working directory web_interface --- use cmd:  python app.py  <enter> follow screen for instructions on navigating to interface via web browser, i.e. http://localhost:5002.   Up and running in about 1 minute.  

# Visual Editor Core

The foundational component of the SpokedPy VPyD that enables bidirectional conversion between visual programming models and Python source code.

## Features

- **Multiple Visual Paradigms**: Support for node-based, block-based, diagram-based, and timeline-based visual programming
- **Bidirectional Conversion**: Seamless conversion between visual models and Python source code
- **17-Language Support**: Universal IR enables translation between Python, JavaScript, TypeScript, Ruby, PHP, Lua, R, Java, Go, Rust, C#, Kotlin, Swift, Scala, C, SQL, and Bash
- **Advanced Python Support**: Handle complex constructs like classes, decorators, async/await, generators, and context managers
- **Code Quality**: Generate high-quality, PEP 8 compliant Python code with type hints and docstrings
- **Extensible Architecture**: Plugin system for custom visual components and code generation rules
- **Property-Based Testing**: Comprehensive test suite with property-based testing for correctness validation

## Architecture

The system follows a layered architecture with clear separation of concerns:

```
Visual Editor UI Layer
       ↓
Visual Model Layer
       ↓
AST Processing Layer
       ↓
Code Generation Layer
```

### Core Components

- **VisualModel**: Internal representation of visual programs
- **ASTProcessor**: Bidirectional conversion between visual models and Python ASTs
- **CodeGenerator**: High-quality Python code generation with formatting and optimization
- **VisualParser**: Converts Python source code back into visual models
- **NodePalette**: Manages available visual components and third-party packages
- **ExecutionEngine**: Live execution and debugging capabilities

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run demo
python demo.py
```

## Quick Start

### Creating a Visual Model

```python
from visual_editor_core import VisualModel, VisualNode, NodeType, InputPort, OutputPort

# Create a visual model
model = VisualModel()

# Add a variable node
var_node = VisualNode(
    type=NodeType.VARIABLE,
    parameters={'variable_name': 'message', 'default_value': 'Hello, World!'},
    outputs=[OutputPort(name='value', data_type=str)]
)
model.add_node(var_node)

# Add a function node
func_node = VisualNode(
    type=NodeType.FUNCTION,
    parameters={'function_name': 'print'},
    inputs=[InputPort(name='value', data_type=str)]
)
model.add_node(func_node)
```

### Converting to Python Code

```python
from visual_editor_core import ASTProcessor, CodeGenerator

# Convert visual model to Python code
processor = ASTProcessor()
generator = CodeGenerator()

ast_tree = processor.visual_to_ast(model)
code = generator.generate_code(ast_tree, {
    'format_code': True,
    'add_type_hints': True,
    'add_docstrings': True
})

print(code)
```

### Parsing Python Code

```python
from visual_editor_core import VisualParser

# Parse Python code into visual model
parser = VisualParser()
python_code = """
x = 42
print(x)
"""

model = parser.parse_code(python_code)
print(f"Parsed {len(model.nodes)} visual nodes")
```

## Supported Python Constructs

- ✅ Variable assignments
- ✅ Function calls and definitions
- ✅ Class definitions with inheritance
- ✅ Control flow (if, for, while)
- ✅ Context managers (with statements)
- ✅ Exception handling (try/except)
- ✅ Async/await patterns
- ✅ Generators and iterators
- ✅ Decorators
- ✅ Metaclasses

## Testing

The project includes comprehensive testing with both unit tests and property-based tests:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_models.py -v          # Core data models
python -m pytest tests/test_ast_processor.py -v   # AST processing
python -m pytest tests/test_code_generator.py -v  # Code generation
python -m pytest tests/test_visual_parser.py -v   # Visual parsing
python -m pytest tests/test_integration.py -v     # Integration tests

# Run property-based tests only
python -m pytest tests/ -v -m property
```

## Design Constraints

- **UI Icons**: Only Lucide icons are accepted (no emojis)
- **Authentication**: Deferred until post-MVP to focus on core visual programming functionality
- **Code Quality**: All generated code must pass standard Python linting tools (pylint, flake8)

## Project Structure

```
visual_editor_core/
├── __init__.py              # Package exports
├── models.py                # Core data models
├── ast_processor.py         # AST processing and conversion
├── code_generator.py        # Python code generation
├── visual_parser.py         # Code to visual parsing
├── node_palette.py          # Component management
└── execution_engine.py      # Live execution and debugging

tests/
├── test_models.py           # Model tests
├── test_ast_processor.py    # AST processor tests
├── test_code_generator.py   # Code generator tests
├── test_visual_parser.py    # Visual parser tests
└── test_integration.py      # End-to-end integration tests
```

## Contributing

1. Ensure all tests pass: `python -m pytest tests/ -v`
2. Follow PEP 8 coding standards
3. Add tests for new functionality
4. Update documentation as needed

## License

MIT
---------------------------------------------------


I enjoyed making this.  I hope you can find something interesting to do with it.  Let me know if you have any questions or issues, more than happy to finally give back to this community.  It's an MIT license, so do what you want with it, it was 7 winter days with Opus 4.6, hopefully this gets me my first github star....lol!


Enjoy,
MattD



