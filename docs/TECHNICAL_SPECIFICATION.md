# SpokedPy: A Polyglot Visual Programming Platform with Event-Sourced State Management and Register-File Execution Architecture

## Technical Specification v2.0

*February 8, 2026*

---

## Abstract

We present SpokedPy, a visual programming platform that unifies source code authoring, cross-language translation, and live execution through four architectural contributions: (1) a **Universal Intermediate Representation** (UIR) that abstracts programming constructs across 17 languages into a language-agnostic semantic model; (2) a **Session Ledger** — a Kafka-inspired, append-only event log that provides immutable state management with full node lineage tracking; (3) a **Node Registry** — a register-file execution matrix with 304 addressable slots across 15 language engine rows, supporting hot-swap code replacement and permissioned inter-slot communication; and (4) a **Single Source of Truth Engine Manifest** — a capability-driven introspection system that derives all engine metadata from the runtime, enabling the platform to self-describe its features, adapt its UI to the host environment, and absorb new languages without configuration changes. The system comprises 81,000+ lines of code across Python, JavaScript, CSS, and HTML, validated by 633 automated tests including property-based verification. This specification formalizes the architecture, defines the data models, establishes the operational semantics, and discusses the theoretical foundations of each subsystem.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Related Work](#2-related-work)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Universal Intermediate Representation](#4-universal-intermediate-representation)
5. [Session Ledger](#5-session-ledger)
6. [Node Registry and Execution Matrix](#6-node-registry-and-execution-matrix)
7. [Language Processing Pipeline](#7-language-processing-pipeline)
8. [Execution Engine Architecture](#8-execution-engine-architecture)
9. [Engine Manifest and Capability System](#9-engine-manifest-and-capability-system)
10. [Visual Paradigm Layer](#10-visual-paradigm-layer)
11. [Parallax Code Rendering System](#11-parallax-code-rendering-system)
12. [AST-Grep Structural Refactoring](#12-ast-grep-structural-refactoring)
13. [Database and Persistence Architecture](#13-database-and-persistence-architecture)
14. [Web Interface and Runtime](#14-web-interface-and-runtime)
15. [Testing and Verification](#15-testing-and-verification)
16. [Formal Properties and Invariants](#16-formal-properties-and-invariants)
17. [Performance Characteristics](#17-performance-characteristics)
18. [Limitations and Future Work](#18-limitations-and-future-work)
19. [Conclusion](#19-conclusion)

---

## 1. Introduction

### 1.1 Problem Statement

Modern software development increasingly requires polyglot literacy. A typical production system may involve Python for machine learning, TypeScript for frontend interfaces, Rust for performance-critical data processing, Go for networked services, and Bash for orchestration. Existing development environments treat each language as an isolated domain: separate editors, separate debuggers, separate mental models. Cross-language understanding requires developers to mentally translate between syntactic and semantic conventions — a cognitively expensive process that scales poorly with language count.

Visual programming systems have historically addressed cognitive complexity by providing graphical abstractions, but existing approaches suffer from three fundamental limitations:

1. **Language lock-in**: Systems like Scratch, Blockly, and Node-RED target a single language or domain-specific abstraction, offering no path to polyglot development.
2. **Fidelity loss**: Low-code/no-code platforms abstract away language details, making it impossible to work with production code directly.
3. **Stateless interaction**: Traditional visual editors do not preserve the history of how a program was constructed, losing valuable provenance information.
4. **Code opacity**: Visual programming nodes are opaque boxes — you must click, open a panel, and switch context to see what a node actually does. The code is hidden behind interaction barriers.

### 1.2 Contributions

SpokedPy addresses these limitations through four architectural innovations:

**C1 — Universal Intermediate Representation (UIR):** A normalized, language-agnostic data model that captures the semantic intent of programming constructs — functions, classes, variables, data flows, type signatures, purity levels, and complexity annotations — enabling bidirectional translation between 17 programming languages through a common bridge representation.

**C2 — Session Ledger:** An append-only, immutable event log (inspired by Apache Kafka's log-structured architecture) that records every mutation in a visual programming session. Node state is never stored directly; it is derived by replaying the event stream, providing complete audit trails, time-travel state reconstruction, and a foundation for conflict-free collaborative editing.

**C3 — Node Registry (Execution Matrix):** A register-file-inspired execution model with 304 addressable slots across 15 language engine rows. Each slot holds a committed node whose code is version-tracked against the ledger. Engines process their slots in a continuous loop, performing hot-swap code replacement when newer versions are detected — achieving continuous integration semantics within the development environment itself.

**C4 — Engine Manifest and Capability System:** A self-describing introspection layer that derives all engine metadata — availability, version, capabilities, tier, parser class — from the runtime at startup, with lazy re-probing for post-startup changes. This enables capability-driven UI adaptation, eliminates hard-coded feature matrices, and reduces the cost of adding a new language to three lines of code.

### 1.3 Scope

This specification covers the system as implemented in February 2026: 72 core library modules (38,900+ lines), a web interface (32,600+ lines across Python, JavaScript, CSS, HTML), and a test suite of 633 tests (9,400+ lines). The platform supports 17 languages for parsing and code generation, 15 engines for execution, and 4 visual programming paradigms.

---

## 2. Related Work

### 2.1 Visual Programming Systems

**Scratch** (Resnick et al., 2009) and **Blockly** (Pasternak et al., 2017) demonstrate the effectiveness of block-based visual programming for education but are limited to single-language targets (Scratch's custom VM, Blockly's JavaScript output). **Node-RED** (IBM, 2013) provides flow-based programming for IoT but operates at the message-passing level rather than the source-code level. **Unreal Engine Blueprints** (Epic Games) offer production-grade visual scripting but are locked to the Unreal ecosystem. SpokedPy differs from all of these by operating on **actual source code** across multiple languages, not on simplified abstractions, and by rendering that code *inside* the visual nodes with zoom-responsive detail — eliminating the opacity problem that plagues all existing visual programming systems.

### 2.2 Intermediate Representations

Compiler IRs such as **LLVM IR** (Lattner & Adve, 2004), **WebAssembly** (Haas et al., 2017), and **GraalVM's Truffle** (Würthinger et al., 2013) provide language-agnostic execution substrates but operate at a level too low for source-level visual manipulation. **Tree-sitter** (Brunsfeld, 2018) provides universal parsing but does not include code generation. SpokedPy's UIR operates at the **semantic level** — capturing intent (function purpose, purity, complexity) rather than instruction sequences — enabling meaningful visual representation and cross-language translation.

### 2.3 Event Sourcing in Development Tools

**Git** (Torvalds, 2005) provides version control through snapshots and diffs but does not capture fine-grained editing events. **Operational Transformation** (Ellis & Gibbs, 1989) and **CRDTs** (Shapiro et al., 2011) enable collaborative editing but require complex conflict resolution. SpokedPy's Session Ledger adopts Apache Kafka's log-structured model (Kreps et al., 2011) — events are ordered, immutable, and never overwritten — providing a simpler foundation for collaboration while maintaining complete operational history.

### 2.4 Register-File Architectures

Hardware register files (Patterson & Hennessy, 2013) provide fast, addressable storage for CPU operands. The concept of register allocation and scheduling has been extensively studied in compiler theory. SpokedPy applies this model at the *software runtime* level: execution slots are analogous to registers, engine loops are analogous to pipeline stages, and hot-swap is analogous to register renaming. To our knowledge, this is the first application of register-file semantics to a visual programming execution environment.

### 2.5 Structural Code Search and Refactoring

**ast-grep** (Herrington, 2022) provides AST-based pattern matching for code search and transformation. **Semgrep** (r2c, 2020) and **Comby** (Haan & Nadi, 2019) offer similar structural matching. **OpenRewrite** (Moderne, 2021) provides large-scale automated refactoring for Java. SpokedPy's integration of ast-grep is unique in that it operates on a **visual, polyglot canvas** rather than a file system — pattern matches are visualized as node decorations, and refactoring is applied selectively through a visual interface that spans multiple languages simultaneously.

---

## 3. System Architecture Overview

### 3.1 Layered Architecture

The system is organized into seven architectural layers, each with well-defined interfaces:

```
┌─────────────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                         │
│  Web Interface · Canvas · 4 Visual Paradigms · Dark UI      │
│  Parallax Code Preview · Syntax-Highlighted SVG Nodes       │
├─────────────────────────────────────────────────────────────┤
│                  RUNTIME LAYER                              │
│  Node Registry · 15 Executors · Multi-Debugger · WebSocket  │
│  Engine Manifest · Capability System · Lazy Re-Probe        │
├─────────────────────────────────────────────────────────────┤
│                  REFACTORING LAYER                          │
│  AST-Grep Integration · Pattern Search · Visual Tagging     │
│  Selective Refactoring · Cross-Language Pattern Matching     │
├─────────────────────────────────────────────────────────────┤
│                  TRANSLATION LAYER                          │
│  UIR Translator · 17 Parsers · 17 Generators · Import Xlat │
├─────────────────────────────────────────────────────────────┤
│                  STATE MANAGEMENT LAYER                     │
│  Session Ledger · Event Log · Node Snapshots · Lineage      │
├─────────────────────────────────────────────────────────────┤
│                  CORE MODEL LAYER                           │
│  Universal IR · Visual Model · AST Processor · Code Gen     │
├─────────────────────────────────────────────────────────────┤
│                  PERSISTENCE LAYER                          │
│  Database Manager · Connection Pool · Migrations · Tenancy  │
│  Project Persistence · Staging Pipeline · Audit Log         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

The canonical data flow for importing and executing code follows this path:

```
Source File (Language L₁)
    │
    ▼
Parser(L₁) → UniversalModule{functions, classes, variables, imports}
    │
    ▼
UIR Translator → NodeSnapshot[] (ledger entries created)
    │
    ▼
Session Ledger ← LedgerEntry{event_type, node_id, payload, timestamp}
    │
    ▼
Visual Canvas ← render(NodeSnapshot[]) → Parallax Code Preview
    │                                      ├── Zoom-responsive line count
    │                                      ├── Inverse-scaled fonts
    │                                      ├── Syntax-highlighted SVG tspans
    │                                      └── Depth-layer parallax transform
    │
    ▼
AST-Grep Search ← pattern_match(canvas_nodes) → Visual Tags
    │
    ▼
Node Registry ← commit(node_id, slot_position)
    │
    ▼
Engine Loop → execute(slot.code) → hot_swap(if version_mismatch)
    │
    ▼
Generator(L₂) → Source File (Language L₂)
```

### 3.3 Module Inventory

| Directory | Files | Lines | Purpose |
|-----------|-------|-------|---------|
| `visual_editor_core/` | 72 | 38,900+ | Core library: IR, parsers, generators, ledger, registry, engines |
| `visual_editor_core/database/` | 16 | ~8,000 | Database abstraction, migrations, multi-tenancy |
| `web_interface/` | 12+ | ~32,600 | Flask server, JavaScript UI, CSS styles, runtime |
| `tests/` | 23 | 9,400+ | Automated test suite |
| **Total** | **123+** | **81,000+** | |

---

## 4. Universal Intermediate Representation

### 4.1 Design Goals

The UIR must satisfy five properties:

1. **Language neutrality** — No construct specific to any single language
2. **Semantic completeness** — Capture intent, not syntax (what a function *does*, not how it's *spelled*)
3. **Bidirectional fidelity** — Support lossless round-trip: parse → UIR → generate → parse → UIR (semantic equivalence)
4. **Visual representability** — Every UIR construct must map to a renderable visual node with inline code preview
5. **Composability** — UIR elements must combine without loss of information

### 4.2 Core Data Model

The UIR is defined as a set of dataclasses forming a hierarchical type system:

#### 4.2.1 Type System

```
DataType ::= VOID | BOOLEAN | INTEGER | FLOAT | STRING
           | ARRAY | OBJECT | FUNCTION | ANY | UNKNOWN

TypeSignature {
    base_type    : DataType
    generic_params : List[TypeSignature]     -- e.g., Array<String>
    nullable     : Boolean
}
```

The type system is deliberately coarse-grained. It maps common types across languages (Python's `int` → `INTEGER`, Rust's `i32` → `INTEGER`, JavaScript's `number` → `INTEGER ∪ FLOAT`) while preserving enough specificity for meaningful visual display and connection validation.

#### 4.2.2 Function Model

```
PurityLevel ::= PURE | READ_ONLY | SIDE_EFFECTS | IO_BOUND | ASYNC

Parameter {
    name       : String
    type_sig   : TypeSignature
    default    : Optional[Any]
    required   : Boolean
}

Contract {
    description : String
    type_sig    : TypeSignature
    constraints : List[String]      -- e.g., "n >= 0"
    examples    : List[Any]
}

SemanticDescription {
    purpose          : String
    input_contracts  : List[Contract]
    output_contract  : Contract
    side_effects     : List[String]
    complexity       : String       -- Big-O notation, e.g., "O(n log n)"
    purity           : PurityLevel
}

UniversalFunction {
    id                  : UUID
    name                : String
    parameters          : List[Parameter]
    return_type         : TypeSignature
    semantics           : Optional[SemanticDescription]
    source_language     : String
    source_code         : String
    implementation_hints: Map[String, Any]   -- language-specific metadata
    dependencies        : List[UUID]         -- references to other functions
    external_libraries  : List[String]
}
```

The `implementation_hints` field is critical: it stores language-specific information that cannot be represented in the universal model but is needed for faithful code generation. For example, Python decorators, Rust lifetime annotations, or Go goroutine markers are stored as hints rather than modeled universally.

#### 4.2.3 Class Model

```
UniversalClass {
    id                  : UUID
    name                : String
    methods             : List[UniversalFunction]
    properties          : List[Parameter]
    base_classes        : List[String]
    source_language     : String
    source_code         : String
    implementation_hints: Map[String, Any]
}
```

#### 4.2.4 Module and Project Models

```
UniversalModule {
    id              : UUID
    name            : String
    functions       : List[UniversalFunction]
    classes         : List[UniversalClass]
    variables       : List[UniversalVariable]
    imports         : List[String]
    exports         : List[String]
    source_language : String
    source_file     : String
}

UniversalProject {
    id                  : UUID
    name                : String
    modules             : List[UniversalModule]
    data_flows          : List[DataFlow]
    language_mappings   : Map[String, Map[String, Any]]
    bridge_requirements : List[String]
}

DataFlow {
    id           : UUID
    source_id    : UUID
    source_output: String
    target_id    : UUID
    target_input : String
    data_type    : TypeSignature
}
```

### 4.3 Language Mapping

The `LanguageMapping` class provides bidirectional translation tables between UIR types/concepts and language-specific implementations:

| UIR Concept | Python | JavaScript | Rust | Go | Java |
|-------------|--------|------------|------|----|------|
| `BOOLEAN` | `bool` | `boolean` | `bool` | `bool` | `boolean` |
| `INTEGER` | `int` | `number` | `i64` | `int64` | `long` |
| `STRING` | `str` | `string` | `String` | `string` | `String` |
| `ARRAY` | `List` | `Array` | `Vec` | `[]` | `ArrayList` |
| `async_function` | `async def` | `async function` | `async fn` | goroutine | `CompletableFuture` |
| `null_check` | `is None` | `== null` | `Option::is_none()` | `== nil` | `== null` |
| `string_interpolation` | f-string | template literal | `format!()` | `fmt.Sprintf()` | `String.format()` |

### 4.4 Formal Properties

**Property 4.1 (Semantic Preservation):** For any source program $P$ in language $L_1$, let $U = \text{parse}_{L_1}(P)$ be its UIR representation and $P' = \text{generate}_{L_2}(U)$ be the generated code in language $L_2$. Then $P'$ is **semantically equivalent** to $P$ with respect to observable behavior: for all inputs $I$, $\text{eval}_{L_1}(P, I) = \text{eval}_{L_2}(P', I)$, modulo language-specific runtime differences (e.g., integer overflow semantics).

**Property 4.2 (Completeness):** The UIR can represent any programming construct expressible in at least two of the 17 supported languages. Constructs unique to a single language (e.g., Python metaclasses, Rust borrow semantics) are preserved in `implementation_hints` but not universally modeled.

**Property 4.3 (Information Preservation):** For any UIR element $u$, $u.\text{source\_code}$ always contains the original source text. Even if the UIR model loses fidelity during translation, the original code is never destroyed and can always be emitted as a comment in the target language.

---

## 5. Session Ledger

### 5.1 Architecture

The Session Ledger implements an **append-only, ordered event log** modeled after Apache Kafka's partition semantics. The analogy is precise:

| Kafka Concept | Session Ledger Equivalent |
|---------------|--------------------------|
| Topic | Session (identified by UUID) |
| Partition | The session's event stream |
| Message | `LedgerEntry` (immutable) |
| Offset | `sequence_number` (monotonically increasing, starting at 10000) |
| Consumer group offset | `NodeSnapshot` (materialized view) |
| Schema registry | `LanguageID` enum (permanent, never reassigned) |

### 5.2 Language Registry

Languages are assigned **permanent integer identifiers** that never change, organized by category:

```
100–119: High-level interpreted    (Python=100, JavaScript=101, ..., Bash=107, Perl=108)
120–139: Compiled / systems        (Go=120, Rust=121, C=122, C++=123)
140–159: JVM / managed runtime     (Java=140, Kotlin=141, Scala=142, C#=143, Swift=144)
160–179: Specialty / domain        (SQL=160, HTML=161, CSS=162)
    0  : Universal IR (language-agnostic)
   -1  : Unknown
```

This registry is immutable: once a language ID is assigned, it is never reassigned or removed, even if the language is deprecated from the execution matrix.

### 5.3 Event Model

#### 5.3.1 Event Types

```
LedgerEventType ::=
    -- Session lifecycle
    | SESSION_CREATED | SESSION_CLOSED
    -- Import events
    | FILE_IMPORTED | REPOSITORY_IMPORTED
    -- Node events
    | NODE_CREATED | NODE_DELETED | NODE_MOVED
    | NODE_CODE_EDITED | NODE_PARAMS_CHANGED
    | NODE_LANGUAGE_CHANGED | NODE_TYPE_CHANGED | NODE_IO_CHANGED
    -- Connection events
    | CONNECTION_CREATED | CONNECTION_DELETED
    -- Export events
    | EXPORT_STARTED | EXPORT_COMPLETED
    -- Execution events
    | NODE_EXECUTED | EXECUTION_BATCH
    -- Conversion events
    | LANGUAGE_CONVERSION | BULK_CONVERSION
```

#### 5.3.2 Entry Structure

```
LedgerEntry (frozen/immutable) {
    entry_id          : String      -- session_id + "-" + sequence_number
    session_id        : UUID        -- parent session
    sequence_number   : Integer     -- monotonically increasing (≥ 10000)
    timestamp         : Float       -- Unix timestamp (microsecond precision)
    event_type        : LedgerEventType
    node_id           : Optional[UUID]
    connection_id     : Optional[UUID]
    source_language_id: Optional[LanguageID]
    target_language_id: Optional[LanguageID]
    canvas_language_id: Optional[LanguageID]
    payload           : String      -- JSON-encoded event data
    import_session_number : Optional[Integer]
    creation_order        : Optional[Integer]
    global_order          : Optional[Integer]
}
```

The `frozen=True` constraint on the dataclass enforces immutability at the Python level. Once a `LedgerEntry` is created, no field can be modified.

### 5.4 Node Snapshot (Materialized View)

A `NodeSnapshot` is the **current state** of a node, derived by replaying all `LedgerEntry` records for that `node_id`:

```
NodeSnapshot {
    node_id              : UUID
    node_type            : String
    display_name         : String
    raw_name             : String

    -- Language lineage (tripartite tracking)
    original_language_id : LanguageID
    current_language_id  : LanguageID
    canvas_language_id   : LanguageID

    -- Source code
    original_source_code : String       -- immutable: code as first imported
    current_source_code  : String       -- mutable: latest version after edits

    -- Structure
    parameters           : Map[String, Any]
    inputs               : List[PortDefinition]
    outputs              : List[PortDefinition]
    metadata             : Map[String, Any]

    -- Provenance
    import_session_number      : Integer
    creation_order_in_import   : Integer
    global_creation_order      : Integer
    source_file                : String

    -- Version tracking
    version              : Integer
    code_versions        : List[VersionRecord]

    -- Flags
    is_modified          : Boolean
    is_converted         : Boolean
    is_connected         : Boolean
}
```

### 5.5 Dependency Strategy

The import pipeline supports four modes of dependency handling:

| Strategy | Depth | Behavior |
|----------|-------|----------|
| `IGNORE` | 0 | Strip all import statements; user manages dependencies manually |
| `PRESERVE` | 1 | Keep import statements as string references (default) |
| `CONSOLIDATE` | 2 | Resolve dependencies, pull source into project as additional nodes |
| `REFACTOR_EXPORT` | Pipeline | Consolidate + immediate re-export with dependencies inlined |

### 5.6 Formal Properties

**Property 5.1 (Append-Only Monotonicity):** For any session $S$, if entry $e_i$ has sequence number $s_i$ and entry $e_j$ has sequence number $s_j$, and $e_i$ was created before $e_j$, then $s_i < s_j$. No entry can be inserted between existing entries, and no entry can be deleted.

**Property 5.2 (State Derivability):** For any node $n$ at time $t$, the node's state $\text{state}(n, t)$ is uniquely determined by replaying all entries $\{e \in S \mid e.\text{node\_id} = n.\text{id} \wedge e.\text{timestamp} \leq t\}$ in sequence number order. Two replays of the same prefix always produce the same state.

**Property 5.3 (Lineage Completeness):** For any node $n$ in the export phase, the system can produce a complete provenance chain: original source file → original language → all edits → all translations → current state. No information about a node's history is ever lost.

**Property 5.4 (Session Isolation):** Events in session $S_1$ cannot reference node IDs created in session $S_2$, unless explicitly imported via a `REPOSITORY_IMPORTED` event. Sessions are causally independent.

---

## 6. Node Registry and Execution Matrix

### 6.1 Register-File Analogy

The Node Registry maps the concepts of hardware register files to software execution:

| Hardware Concept | Registry Equivalent |
|-----------------|---------------------|
| Register file | The full 304-slot matrix |
| Register | `RegistrySlot` — addressable cell holding one committed node |
| Pipeline stage | `EngineRow` — a language runtime processing its slots in a loop |
| Register value | Node's compiled/interpreted code + execution state |
| Register renaming | Hot-swap: old code finishes, new version loads on next tick |
| Instruction issue | `commit()` — placing a node into a slot |
| Write-back | Storing execution output back to the slot's `output_buffer` |
| Inter-register forwarding | Slot-to-slot communication via GET/PUSH API |

### 6.2 Engine Definition

```
EngineID ::=
    PYTHON(a, 64)     | JAVASCRIPT(b, 16)  | TYPESCRIPT(c, 16) | RUST(d, 16)
  | JAVA(e, 16)       | SWIFT(f, 16)       | CPP(g, 16)        | R(h, 16)
  | GO(i, 16)         | RUBY(j, 16)        | CSHARP(k, 16)     | KOTLIN(l, 16)
  | C(m, 16)          | BASH(n, 16)        | PERL(o, 16)

EngineRow {
    engine_id       : EngineID
    max_slots       : Integer
    slots           : Map[Integer, RegistrySlot]
    is_running      : Boolean
    loop_tick_count : Integer
    loop_interval_ms: Integer          -- default 100ms
}
```

The asymmetric allocation (64 Python slots vs. 16 for others) reflects the platform's Python-centric design while maintaining language parity in the architecture.

### 6.3 Slot Model

```
RegistrySlot {
    slot_id                : String    -- "nra{NN}" global address
    engine_id              : String    -- EngineID name
    position               : Integer   -- 1-indexed column in engine row

    -- Committed content
    node_id                : Optional[UUID]
    node_name              : String
    committed_version      : Integer
    last_executed_version  : Integer

    -- Execution state
    last_output            : String
    last_error             : String
    last_execution_time    : Float
    execution_count        : Integer
    last_executed_at       : Float

    -- Communication buffers
    input_buffer           : List[Message]
    output_buffer          : List[Message]

    -- Permissions
    permissions            : SlotPermissionSet{get, push, post, delete}

    -- Flags
    is_active              : Boolean
    is_dirty               : Boolean
    is_paused              : Boolean
}
```

### 6.4 Addressing Scheme

Slots are addressed in two complementary schemes:

1. **Global address**: `nra{NN}` where `NN` is a 1-indexed global slot number (e.g., `nra01`, `nra64`, `nra65`)
2. **Matrix address**: `{engine_letter}{position}` (e.g., `a1` = Python slot 1, `b3` = JavaScript slot 3, `o16` = Perl slot 16)

The global address provides a flat namespace for REST API routing:
```
GET  /api/nra{NN}/        → Read slot output
POST /api/nra{NN}/push    → Push data to slot input buffer
POST /api/nra{NN}/post    → Trigger execution
DEL  /api/nra{NN}/        → Clear/reset slot
```

### 6.5 Hot-Swap Protocol

The hot-swap mechanism ensures zero-downtime code updates:

```
Algorithm: ENGINE_LOOP(engine_row)
    WHILE engine_row.is_running:
        FOR EACH slot IN engine_row.slots:
            IF slot.is_paused OR NOT slot.is_active:
                CONTINUE

            IF slot.needs_hot_swap():
                new_code ← ledger.get_current_source(slot.node_id)
                slot.load_code(new_code)
                slot.last_executed_version ← slot.committed_version
                slot.is_dirty ← FALSE

            IF slot.has_pending_input():
                result ← execute(slot.code, slot.input_buffer)
                slot.last_output ← result.output
                slot.last_error ← result.error
                slot.execution_count += 1
                slot.output_buffer.append(result)

        engine_row.loop_tick_count += 1
        SLEEP(engine_row.loop_interval_ms)
```

**Property 6.1 (Hot-Swap Safety):** A slot's code is only replaced between executions, never during one. The engine completes the current execution of the old version before loading the new version. This ensures execution atomicity.

**Property 6.2 (Version Monotonicity):** `slot.last_executed_version` is monotonically non-decreasing. The engine never reverts to an older version unless explicitly commanded via the DEL API.

### 6.6 Permission Model

Each slot has a `SlotPermissionSet` controlling external access:

```
SlotPermission ::= GET | PUSH | POST | DEL

SlotPermissionSet {
    get    : Boolean    -- default: TRUE
    push   : Boolean    -- default: FALSE
    post   : Boolean    -- default: FALSE
    delete : Boolean    -- default: FALSE
}
```

---

## 7. Language Processing Pipeline

### 7.1 Parser Architecture

Each of the 17 supported languages has a dedicated parser module:

```
{language}_parser.py → class {Language}Parser:
    def parse(source_code: str) → UniversalModule
    def _extract_functions(source: str) → List[UniversalFunction]
    def _extract_classes(source: str) → List[UniversalClass]
    def _extract_variables(source: str) → List[UniversalVariable]
    def _extract_imports(source: str) → List[str]
    def _extract_control_flow(source: str) → Dict[str, Any]
```

**Python parser**: Uses `ast.parse()` for full AST analysis, providing the highest fidelity. Handles decorators, async/await, generators, context managers, metaclasses, and complex comprehensions.

**Other parsers**: Use regex-based pattern matching and structural heuristics. This provides sufficient fidelity for function/class extraction and type inference.

### 7.2 Generator Architecture

Each language has a corresponding generator producing **idiomatic** code for its target language.

### 7.3 Cross-Language Import Translation

The `ImportTranslator` module handles the non-trivial problem of translating import statements between languages:

```
Python:     from os import path       →  Rust:       use std::path::Path;
Python:     import json               →  JavaScript: const json = require('json');
Python:     from typing import List   →  TypeScript: // (built-in, no import needed)
Python:     import numpy as np        →  R:          library(numpy)  # approximate
```

### 7.4 Translation Pipeline

The full translation pipeline from language $L_1$ to language $L_2$:

$$P_{L_2} = \text{Generator}_{L_2}(\text{ImportTranslator}(\text{Parser}_{L_1}(P_{L_1}), L_2))$$

---

## 8. Execution Engine Architecture

### 8.1 Executor Class Hierarchy

Each of the 15 execution engines is implemented as a dedicated executor class in `execution_engine.py` (1,800+ lines):

| Executor Class | Language | Binary | Discovery Strategy |
|----------------|----------|--------|-------------------|
| `PythonExecutor` | Python | `python` | `sys.executable` — always available |
| `JavaScriptExecutor` | JavaScript | `node` | `shutil.which('node')` |
| `TypeScriptExecutor` | TypeScript | `tsx` / `ts-node` / `npx` | Cascading fallback chain |
| `RustExecutor` | Rust | `rustc` | `shutil.which('rustc')` + lazy re-probe |
| `JavaExecutor` | Java | `javac` + `java` | `shutil.which('javac')` |
| `GoExecutor` | Go | `go` | `shutil.which('go')` |
| `CExecutor` | C | `gcc` / `cc` | `shutil.which('gcc')` with fallback |
| `CppExecutor` | C++ | `g++` / `clang++` | Multi-binary search |
| `CSharpExecutor` | C# | `dotnet-script` / `dotnet` / `csc` | 3-tier strategy with runtime enumeration |
| `KotlinExecutor` | Kotlin | `kotlinc` | `shutil.which('kotlinc')` |
| `SwiftExecutor` | Swift | `swift` | `shutil.which('swift')` |
| `RubyExecutor` | Ruby | `ruby` | `shutil.which('ruby')` |
| `RExecutor` | R | `Rscript` | `shutil.which('Rscript')` |
| `BashExecutor` | Bash/PowerShell | `bash` / `powershell` | Multi-shell with translator |
| `PerlExecutor` | Perl | `perl` | `shutil.which('perl')` + well-known paths |

### 8.2 Bash-to-PowerShell Translation

The `BashExecutor` includes a transparent **Bash→PowerShell translator** for Windows environments. When no Unix shell (`bash`, `sh`) is found, the executor searches for `pwsh` or `powershell` and translates shell scripts at execution time:

| Bash Construct | PowerShell Translation |
|---------------|----------------------|
| `for i in $(seq 1 $n); do ... done` | `foreach ($i in 1..$n) { ... }` |
| `echo "text"` | `Write-Output "text"` |
| `$(nproc)` | `(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors` |
| `$(date)` | `(Get-Date -Format 'ddd MMM dd HH:mm:ss yyyy')` |
| `$(uname -s)` | `[System.Environment]::OSVersion.Platform` |
| `$(uname -r)` | `[System.Environment]::OSVersion.Version.ToString()` |
| `$(hostname)` | `[System.Net.Dns]::GetHostName()` |

The translator handles embedded command substitution, for/seq/done loops, echo commands, and prepends a UTF-8 BOM to `.ps1` files for correct encoding on Windows. The translation is invisible to the user — they author Bash, they see correct output.

### 8.3 Lazy Re-Probe

Executors cache their binary paths at initialization for performance. However, the user may install a runtime *after* the server starts. The system addresses this through **lazy re-probing**:

1. **At execute time**: If the cached path is `None`, the executor re-runs `shutil.which()` before reporting failure. If found, the path is cached for subsequent calls.
2. **At manifest time**: The `/api/engines` endpoint checks each executor's cached path. If `None`, it probes `shutil.which()` with a language-specific binary name list and, if found, updates the executor's cached path via `setattr()`.

This means a freshly installed `rustc` or `perl` binary is discovered on the next API call or execution attempt, without a server restart.

### 8.4 Perl Executor with Well-Known Path Search

The `PerlExecutor` demonstrates the platform's approach to runtime discovery. Beyond `shutil.which('perl')`, it searches well-known installation directories:

```python
_EXTRA_SEARCH = [
    r'c:\strawberry\perl\bin\perl.exe',      # Strawberry Perl (Windows)
    r'c:\perl\bin\perl.exe',                  # ActivePerl (Windows)
    '/usr/bin/perl',                           # Linux/macOS
    '/usr/local/bin/perl',                     # Homebrew (macOS)
]
```

---

## 9. Engine Manifest and Capability System

### 9.1 The Single Source of Truth

The `/api/engines` endpoint is the platform's canonical engine manifest. It does not read from a configuration file or database — it **derives everything from the runtime**:

1. **Enumerate `EngineID`**: Walk the enum to get all engine letters, language IDs, and slot capacities
2. **Resolve executor**: Look up the per-language executor instance from the `_executors` pool
3. **Probe availability**: Check the executor's cached binary path; lazy re-probe if `None`
4. **Detect version**: Run the runtime binary with `--version` (or language-specific flag) and parse the output
5. **Assign capabilities**: Look up the engine's feature flags (REPL, debug, canvas execution, AST parsing, export, import)
6. **Classify tier**: Primary (Python), tier-1 (JS, TS, Rust, Java, Go), or tier-2 (all others)

### 9.2 Manifest Schema

```json
{
  "success": true,
  "engines": [
    {
      "letter":           "a",
      "name":             "Python",
      "language":         "python",
      "max_slots":        64,
      "extension":        "py",
      "platform_enabled": true,
      "runtime_version":  "Python 3.13.5",
      "runtime_path":     "C:\\Python313\\python.exe",
      "capabilities": {
        "repl":        true,
        "debug":       true,
        "canvas_exec": true,
        "engine_tab":  true,
        "export":      true,
        "import_file": true,
        "ast_parse":   true
      },
      "parser":           "PythonExecutor",
      "tier":             "primary"
    }
  ],
  "total":    15,
  "enabled":  8,
  "disabled": 7
}
```

### 9.3 Capability Flags

| Capability | Description | Engines with Flag |
|-----------|-------------|-------------------|
| `repl` | Persistent namespace across executions | Python only |
| `debug` | Breakpoints, step execution, variable inspection | Python, JavaScript, TypeScript |
| `canvas_exec` | Execute code directly from canvas nodes | All 15 engines |
| `engine_tab` | Dedicated tab in the live execution panel | All 15 engines |
| `export` | Export code as a standalone source file | All 15 engines |
| `import_file` | Import source files from disk | All 15 engines |
| `ast_parse` | Full AST analysis (not just regex) | Python, JavaScript, TypeScript |

### 9.4 Frontend Consumption

On page load, `live-execution.js` calls `_loadEngineManifest()` which fetches `/api/engines` and overwrites hardcoded defaults:

```javascript
// All maps exposed as window.* globals for cross-module access
window.ENGINE_NAMES        = {};   // letter → display name
window.ENGINE_SLOTS        = {};   // letter → max slot count
window.ENGINE_LETTERS      = [];   // ordered engine letters
window.LANG_TO_EXT         = {};   // language → file extension
window.LETTER_TO_LANG      = {};   // letter → language string
window.ENGINE_CAPABILITIES = {};   // letter → capability dict
window.ENGINE_TIERS        = {};   // letter → tier string
window.ENGINE_PARSERS      = {};   // letter → parser class name
window.ENGINE_VERSIONS     = {};   // letter → version string
```

This means the runtime panel (`runtime-panel.js`), the main app (`app.js`), and any future modules can read `window.ENGINE_*` without importing their own copies. **There is one source of truth, and it flows from the Python enum through the REST API to every JavaScript module.**

### 9.5 The Three-Line Extension Contract

Adding a new language to SpokedPy requires exactly three changes:

1. `session_ledger.py` — Add a `LanguageID` constant (e.g., `PERL = 108`)
2. `node_registry.py` — Add an `EngineID` tuple (e.g., `PERL = ('o', LanguageID.PERL, 16)`)
3. `execution_engine.py` — Write an executor class (e.g., `PerlExecutor`) and register it in `EXECUTOR_CLASSES`

Everything else — the engine manifest, the frontend maps, the registry slots, the matrix visualization, the export extensions, the download code function — is derived automatically. This is not convenience; it is an architectural invariant that eliminates consistency bugs.

---

## 10. Visual Paradigm Layer

### 10.1 Supported Paradigms

| Paradigm | Best For | Node Style | Connection Style |
|----------|----------|------------|-----------------|
| **Node-Based** | Data flow, functional composition | Rectangular blocks with input/output ports | Directed edges (data flow) |
| **Block-Based** | Control flow, imperative programming | Nested blocks (Scratch-style) | Structural nesting |
| **Diagram-Based** | OOP design, class relationships | UML-style class boxes | Inheritance, composition arrows |
| **Timeline-Based** | Async operations, event sequencing | Horizontal timeline bars | Temporal ordering |

### 10.2 Paradigm Manager

The `ParadigmManager` enables **live paradigm switching**: a program created in node-based view can be switched to diagram-based view without losing information, because both paradigms render from the same underlying UIR.

---

## 11. Parallax Code Rendering System

### 11.1 Design Philosophy

Traditional visual programming nodes are **opaque containers** — labeled boxes that reveal their contents only when clicked. This creates a fundamental cognitive friction: the developer must constantly switch between spatial reasoning (where nodes are, how they connect) and textual reasoning (what the code does). SpokedPy eliminates this friction by rendering source code *directly inside* every node, with zoom-responsive detail and parallax depth effects.

### 11.2 Rendering Pipeline

The code rendering pipeline operates per-node on every zoom change:

```
1. Extract source_code from node.parameters.source_code
2. Calculate zoom-dependent metrics:
   - fontSize = 9 / zoom                              (inverse scaling)
   - lineHeight = fontSize × 1.6
   - linesToShow = clamp(2 × zoom, 2, 10)             (zoom-proportional)
   - visibleChars = clamp(18 × zoom, 18, 50)          (zoom-proportional)
3. Window the code:
   - Center on the middle of the source
   - Show linesToShow lines, centered vertically
   - Show visibleChars characters per line, centered horizontally
4. Tokenize each visible line:
   - Keywords → .code-keyword  (syntax color)
   - Strings  → .code-string   (syntax color)
   - Numbers  → .code-number   (syntax color)
   - Comments → .code-comment  (syntax color)
5. Render as SVG <tspan> elements within a clipped group
6. Apply parallax transform based on mouse position
```

### 11.3 Parallax Depth Effect

Each code preview group contains two depth layers:

- **Background layer** (`depth = 0.2`): The code background rectangle
- **Text layer** (`depth = 0.4`): The syntax-highlighted code text

The `applyParallaxToCode()` function computes a transform offset based on the mouse position relative to the canvas center:

```
offsetX = (mouseX - canvasCenterX) / canvasWidth
offsetY = (mouseY - canvasCenterY) / canvasHeight

For each layer:
    translateX = offsetX × depth × 6
    translateY = offsetY × depth × 6
    layer.transform = translate(translateX, translateY)
```

This creates a subtle dimensional effect where the code text shifts slightly relative to its background as the mouse moves, giving the impression that the code is *floating within* the node at a distinct depth plane. The effect is intentionally subtle — it serves as a subconscious spatial cue, not a distraction.

### 11.4 Zoom-Level Behavior

| Zoom Level | Lines Visible | Characters/Line | Font Size | User Experience |
|-----------|--------------|-----------------|-----------|----------------|
| 0.5× | 1 | 9 | 18px | See function signatures only |
| 1.0× | 2 | 18 | 9px | See key logic lines |
| 2.0× | 4 | 36 | 4.5px | Read implementation details |
| 3.0× | 6 | 50 | 3px | Full code readability |
| 5.0× | 10 | 50 | 1.8px | Deep inspection |

The inverse scaling (`fontSize = 9 / zoom`) means the rendered code *appears* larger as the canvas zooms in — the SVG coordinates shrink but the viewport magnification compensates, creating a natural reading experience that mimics approaching a physical document.

---

## 12. AST-Grep Structural Refactoring

### 12.1 Integration Architecture

SpokedPy integrates ast-grep through two pathways:

1. **Python bindings** (`ast_grep_py.SgRoot`): Direct in-process AST analysis when the Python package is installed
2. **CLI fallback** (`ast-grep` subprocess): Temporary file-based analysis when only the CLI tool is available

The integration operates on the **canvas level**, not the file system level. Each node's `source_code` is treated as a code fragment for pattern matching.

### 12.2 Pattern Language

AST-grep patterns use a syntax that mirrors the target language:

| Pattern | Matches | Language |
|---------|---------|----------|
| `$func($arg, $arg)` | Any 2-argument function call | Python, JS |
| `for $i in range($n)` | Range-based for loops | Python |
| `$x = $x + 1` | Increment-by-one assignments | Any |
| `if $cond: return $val` | Guard clauses | Python |
| `console.log($msg)` | Console log statements | JavaScript |
| `fn $name($$$) -> $ret` | Functions with return types | Rust |

The `$VAR` syntax captures single AST nodes; `$$$` captures zero or more nodes. Captures are preserved in replacements, enabling semantic-preserving refactoring.

### 12.3 Cross-Language Refactoring

Because the canvas can contain nodes in multiple languages, ast-grep searches operate **across the entire polyglot workspace**. A single refactoring session might:

1. Find `print($msg)` in Python nodes → replace with `logger.info($msg)`
2. Find `console.log($msg)` in JavaScript nodes → replace with `logger.info($msg)`
3. Find `println!($msg)` in Rust nodes → replace with `log::info!($msg)`

All three transformations are previewed simultaneously in the visual tagging interface, and the developer can selectively apply each one.

### 12.4 Visual Tagging System

When a pattern match is found, the matching node receives visual decorations:

- **Green outline**: A colored border indicating the node contains matches
- **Match count badge**: A numeric indicator showing how many matches exist within the node
- **Clickable results**: A result list where clicking navigates to the node on the canvas

Tags can be toggled per-search and cleared individually or globally.

---

## 13. Database and Persistence Architecture

### 13.1 Dual-Database Strategy

The system uses **PostgreSQL as primary** and **SQLite as fallback**, with automatic failover:

```
Application
    │
    ▼
DatabaseManager
    ├─── PostgreSQLAdapter (primary)
    │        ├── Connection Pool (configurable size)
    │        ├── Row-Level Security (tenant isolation)
    │        └── JSONB storage (configurations)
    │
    └─── SQLiteAdapter (fallback)
             ├── File-based storage
             ├── Trigger-based isolation
             └── TEXT JSON storage
```

### 13.2 Project Persistence

The `project_db.py` module provides SQLite-based project persistence:
- **Save**: Serialize canvas state, node data, and ledger entries to a named project
- **Load**: Restore a complete project state from storage
- **List**: Browse saved projects with metadata (name, timestamp, node count)
- **Delete**: Remove projects with cascade cleanup

### 13.3 Staging Pipeline

The `StagingPipeline` provides **speculative execution and promotion**:
- Snippets are staged in a sandbox environment
- Execution results are audited before promotion to production slots
- A JSONL audit log records all staging decisions

---

## 14. Web Interface and Runtime

### 14.1 Server Architecture

```
Flask Application (app.py, ~3,640 lines)
    ├── Canvas API          (Node/connection CRUD)
    ├── Palette API         (Component management)
    ├── AST-Grep API        (Structural search/refactor)
    ├── Paradigm API        (Paradigm switching)
    ├── Repository API      (File/project import)
    ├── UIR Translation API (Cross-language conversion)
    ├── Ledger API          (Session history)
    ├── AI Chat API         (LLM integration)
    └── Export API          (Multi-language export)

Runtime Blueprint (runtime.py, ~2,090 lines)
    ├── Engine Manifest     (/api/engines — single source of truth)
    ├── Registry Routes     (22 endpoints under /api/registry/*)
    ├── Live Execution      (6 endpoints under /api/execution/ledger/*)
    ├── Multi-Debugger      (7 endpoints under /api/execution/multi-debug/*)
    ├── Simultaneous Exec   (/api/execution/engines/run-simultaneous)
    ├── Project Persistence (/api/projects — save/load/list/delete)
    ├── Engine Demos        (/api/demos/engine-tabs — polyglot demos)
    └── WebSocket Handlers  (2 handlers)
```

### 14.2 Frontend Architecture

| File | Lines | Purpose |
|------|-------|---------|
| `app.js` | ~5,556 | Canvas rendering, parallax code preview, paradigm switching |
| `live-execution.js` | ~1,827 | Dual-mode execution panel, engine manifest consumer |
| `runtime-panel.js` | ~862 | Bottom-edge runtime dashboard with 3 adaptive layouts |
| `properties-panel.js` | ~800 | Node property editor |
| `repository-analyzer.js` | ~600 | Repository import interface |
| `ai-chat.js` | ~400 | AI assistant integration |
| `panel-resizer.js` | ~200 | Drag-to-resize panel logic |
| `virtual-scroller.js` | ~200 | Virtual scrolling for large palettes |
| `style.css` | ~3,273 | Dark cyberpunk theme, matrix animations, parallax styles |
| `index.html` | ~702 | Application shell |

### 14.3 Runtime Dashboard

The Runtime Panel (`runtime-panel.js`) provides a **bottom-edge, resizable dashboard** with three adaptive layouts:

| Layout | Height Threshold | Shows |
|--------|-----------------|-------|
| `layout-full` | ≥ 450px | Timeline chart + Engine matrix + Metrics sidebar |
| `layout-medium` | 220–450px | Timeline chart + Engine matrix |
| `layout-compact` | < 220px | Metrics summary only |

The dashboard reads all engine data from `window.ENGINE_*` globals populated by the manifest, ensuring zero duplication of engine metadata.

### 14.4 Execution Modes

**Ledger Mode (REPL):** Executes nodes directly using a persistent Python executor with shared namespace. Variables persist across executions.

**Registry Mode (Matrix):** Commits nodes to registry slots and executes via the engine loop. Supports hot-swap, inter-slot communication, and the full permission model.

---

## 15. Testing and Verification

### 15.1 Test Suite Overview

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_node_registry.py` | 61 | Registry, engines, slots, permissions, hot-swap |
| `test_session_ledger_imports.py` | ~50 | Ledger events, node snapshots, lineage |
| `test_import_pipeline_e2e.py` | ~40 | End-to-end import across languages |
| `test_generator_imports.py` | ~34 | Code generation for all 17 languages |
| `test_parser_imports.py` | ~34 | Parsing for all 17 languages |
| `test_import_translator.py` | ~30 | Cross-language import statement translation |
| `test_ast_processor.py` | ~40 | AST ↔ visual model conversion |
| `test_database_manager.py` | ~40 | Database abstraction layer |
| `test_migration_manager.py` | ~20 | Schema migrations |
| `test_transaction_manager.py` | ~25 | Transaction system |
| `test_multi_tenant_manager.py` | ~20 | Multi-tenancy isolation |
| Other test files | ~154 | Canvas, paradigms, plugins, code gen, integration |
| **Total** | **633** | |

### 15.2 Testing Strategies

- **Property-based testing** (Hypothesis): Validates round-trip conversion properties, type system invariants, and ledger monotonicity across randomized inputs.
- **Integration testing**: End-to-end workflows — import a file, translate it, execute it, export it.
- **Regression testing**: The full suite runs in ~13 minutes; all 632 tests pass (1 pre-existing known failure deselected).

---

## 16. Formal Properties and Invariants

### 16.1 System-Level Invariants

**I1 (Ledger Immutability):** No ledger entry is ever modified or deleted after creation.

**I2 (Sequence Monotonicity):** For any session, entry sequence numbers are strictly monotonically increasing: $\forall i < j: s_i < s_j$.

**I3 (Language ID Permanence):** Language IDs in the `LanguageID` registry are permanent: once assigned, they are never reassigned to a different language.

**I4 (Snapshot Determinism):** Replaying the same set of ledger entries for a given node always produces the same `NodeSnapshot`, regardless of when the replay occurs.

**I5 (Slot Exclusivity):** Each registry slot holds at most one node at any time: $\forall s \in \text{Slots}: |\{n \mid n.\text{slot} = s\}| \leq 1$.

**I6 (Version Consistency):** A slot's `committed_version` is always $\geq$ its `last_executed_version`.

**I7 (Permission Enforcement):** No operation on a slot can bypass its `SlotPermissionSet`.

**I8 (Manifest Derivability):** The engine manifest is fully derivable from the `EngineID` enum, the executor pool, and the host's PATH. No external configuration is required or consulted.

**I9 (Extension Contract):** Adding a new language engine requires exactly three code changes (LanguageID, EngineID, Executor class). All downstream artifacts (manifest, frontend maps, matrix slots, export extensions) are derived automatically.

### 16.2 Composition Theorems

**Theorem 16.1 (Translation Composability):** For languages $L_1, L_2, L_3$:

$$\text{translate}(L_1 \to L_3) \equiv \text{translate}(L_2 \to L_3) \circ \text{translate}(L_1 \to L_2)$$

modulo `implementation_hints` that are language-pair specific.

**Theorem 16.2 (Ledger-Registry Consistency):** For any committed slot $s$ with node $n$:

$$s.\text{committed\_version} = \text{ledger.get\_version}(n.\text{id})$$

at the moment of commit.

---

## 17. Performance Characteristics

### 17.1 Measured Metrics

| Operation | Observed Time | Environment |
|-----------|--------------|-------------|
| Full test suite (633 tests) | ~13 minutes | Python 3.13, Windows |
| Perl execution (hello world) | 116ms | Strawberry Perl 5.42.0 |
| Python execution (typical) | < 50ms | CPython 3.13.5 |
| Go execution (compile + run) | < 500ms | Go 1.25.5 |
| Registry commit | < 10ms | In-memory |
| Engine manifest generation | < 3s | 15 engines, version probing |
| PostgreSQL migration (8 ops) | 0.148s | Local PostgreSQL |
| SQLite migration (8 ops) | 0.014s | Local SQLite |

### 17.2 Capacity

| Resource | Capacity |
|----------|----------|
| Registry slots | 304 (expandable) |
| Execution engines | 15 |
| Languages (parsing + generation) | 17 |
| Ledger entries per session | Unbounded |
| Concurrent debug sessions | Configurable |
| Database connections (pool) | Configurable (default: 5–20) |

---

## 18. Limitations and Future Work

### 18.1 Current Limitations

1. **Control-flow fragmentation**: Inner control-flow blocks (for/while/if/try) extracted as standalone nodes may fail when executed independently. **Mitigation designed**: Execution Groups with parent/child node relationships.

2. **Parser fidelity**: Non-Python parsers use regex/pattern matching rather than language-specific ASTs. Complex constructs may be partially parsed. **Mitigation**: `source_code` preservation ensures no information is lost. Tree-sitter integration planned.

3. **Single-machine deployment**: The registry runs in-process. Distributing slots across machines requires network transport integration.

4. **No real-time collaboration**: The ledger architecture supports multi-user scenarios by design, but the WebSocket layer does not yet implement collaborative cursor tracking.

### 18.2 Planned Enhancements

| Enhancement | Impact | Complexity |
|-------------|--------|------------|
| Execution Groups (parent/child nodes) | Fixes control-flow execution | Medium |
| Tree-sitter integration for parsers | Higher fidelity for all 17 languages | High |
| Distributed registry (network slots) | Horizontal scaling | High |
| LLM-assisted UIR enrichment | Better cross-language semantics | Medium |
| Parser versioning | Per-engine metadata for docs/releases | Low |
| Plugin marketplace | Community-contributed extensions | Medium |
| Real-time collaboration | Multi-user canvas editing | High |
| Visual CI/CD pipeline | Registry as deployment target | High |
| LSP integration | SpokedPy as IDE backend | Medium |

### 18.3 Research Directions

1. **Formal verification of translation correctness**: Can we prove semantic preservation for specific language pairs using SMT solvers?
2. **Optimal slot allocation**: Given nodes with data dependencies, what is the optimal slot assignment minimizing inter-engine communication?
3. **Event-sourced collaborative editing**: Can the ledger serve as a CRDT for real-time multi-user visual programming?
4. **Register-file scheduling for visual programs**: Can compiler-style scheduling algorithms improve execution throughput?
5. **Zoom-responsive information density**: Can the parallax rendering system be extended to show different *kinds* of information at different zoom levels (documentation at 0.3×, code at 1×, AST structure at 3×)?

---

## 19. Conclusion

SpokedPy demonstrates that the combination of a **language-agnostic intermediate representation**, an **event-sourced state management system**, a **register-file execution architecture**, and a **self-describing capability manifest** produces a visual programming platform with capabilities not found in any existing system.

The UIR enables polyglot translation across 17 languages. The Session Ledger provides immutable provenance tracking with time-travel state reconstruction. The Node Registry enables live, hot-swappable, permissioned code execution across 15 simultaneous language engines. The Engine Manifest ensures the platform adapts to its environment and absorbs new languages with minimal code changes. The parallax code rendering system eliminates the opacity barrier that makes traditional visual programming cognitively expensive. And the AST-grep integration provides structural refactoring at a scope — entire polyglot codebases on a visual canvas — that no text editor can represent.

The system is not a theoretical design. It is an 81,000+ line implementation, validated by 633 automated tests, with a fully functional web interface, 15 wired execution engines, enterprise database infrastructure, and multi-tenant security. The architectural foundations are designed for future distribution while functioning effectively in a single-process deployment today.

The thoughtful details — code that reveals itself as you zoom, runtimes that discover themselves, structural patterns that cross language boundaries, shell scripts that execute on any OS — are not features added to an architecture. They are **consequences of an architecture designed to make such features inevitable.**

---

Matthew DiFrancesco


*SpokedPy — Code is data. Data is visual. Visual is executable.*

---

## Appendix A: File Structure

```
SpokedPy/
├── visual_editor_core/                  # Core library (72 files, 38,900+ lines)
│   ├── universal_ir.py                  # UIR data model
│   ├── session_ledger.py                # Event-sourced state (LanguageID, LedgerEntry, NodeSnapshot)
│   ├── node_registry.py                 # Execution matrix (EngineID, RegistrySlot, 304 slots)
│   ├── execution_engine.py              # 15 executor classes (1,800+ lines)
│   ├── uir_translator.py               # Cross-language translation
│   ├── import_translator.py             # Import statement translation
│   ├── models.py                        # Core visual models
│   ├── ast_processor.py                 # AST ↔ visual model
│   ├── ast_grep_integration.py          # Structural code search (668 lines)
│   ├── snippet_staging.py               # Staging pipeline
│   ├── code_generator.py               # Python code generation
│   ├── visual_parser.py                 # Code → visual model
│   ├── execution_visualizer.py          # Real-time execution visualization
│   ├── data_flow_visualizer.py          # Data flow animation
│   ├── node_palette.py                  # Component management
│   ├── canvas.py                        # Visual canvas
│   ├── visual_paradigms.py              # 4 paradigm definitions
│   ├── plugin_system.py                 # Plugin architecture
│   ├── library_node_generator.py        # Standard library node creation
│   ├── {lang}_parser.py                 # 17 language parsers
│   ├── {lang}_generator.py              # 17 language generators
│   └── database/                        # Persistence layer (16 files)
│       ├── database_manager.py          # Unified database interface
│       ├── connection_pool.py           # Connection pooling
│       ├── migration_manager.py         # Schema versioning
│       ├── multi_tenant_manager.py      # Tenant isolation
│       ├── tenant_access_control.py     # Access control enforcement
│       ├── transaction_manager.py       # Transaction coordination
│       ├── deadlock_detector.py         # Wait-for graph analysis
│       └── transaction_monitor.py       # Performance monitoring
├── web_interface/                       # Web application (~32,600 lines)
│   ├── app.py                           # Flask server (~3,640 lines)
│   ├── runtime.py                       # Runtime blueprint (~2,090 lines)
│   ├── project_db.py                    # Project persistence (SQLite)
│   ├── engine_demos.py                  # Polyglot demo tabs
│   └── static/                          # Frontend
│       ├── app.js                       # Canvas, parallax, paradigms (~5,556 lines)
│       ├── live-execution.js            # Execution panel (~1,827 lines)
│       ├── runtime-panel.js             # Runtime dashboard (~862 lines)
│       ├── properties-panel.js          # Node property editor (~800 lines)
│       ├── style.css                    # Dark cyberpunk theme (~3,273 lines)
│       └── ...                          # Additional JS modules
├── tests/                               # Test suite (23 files, 633 tests)
└── project_specs/                       # Design and requirements documents
```

## Appendix B: Supported Languages

| # | Language | Parser | Generator | Engine | Letter | Slots | Runtime (dev machine) |
|---|----------|--------|-----------|--------|--------|-------|----------------------|
| 1 | Python | `ast.parse()` (full AST) | ✅ | ✅ | a | 64 | CPython 3.13.5 |
| 2 | JavaScript | Regex/pattern | ✅ | ✅ | b | 16 | Node.js v20.18.0 |
| 3 | TypeScript | Regex/pattern | ✅ | ✅ | c | 16 | Node.js v20.18.0 (tsx) |
| 4 | Rust | Regex/pattern | ✅ | ✅ | d | 16 | rustc 1.93.0 |
| 5 | Java | Regex/pattern | ✅ | ✅ | e | 16 | JDK 21.0.7 LTS |
| 6 | Swift | Regex/pattern | ✅ | ✅ | f | 16 | — |
| 7 | C++ | Regex/pattern | ✅ | ✅ | g | 16 | — |
| 8 | R | Regex/pattern | ✅ | ✅ | h | 16 | — |
| 9 | Go | Regex/pattern | ✅ | ✅ | i | 16 | go 1.25.5 |
| 10 | Ruby | Regex/pattern | ✅ | ✅ | j | 16 | — |
| 11 | C# | Regex/pattern | ✅ | ✅ | k | 16 | .NET 9.0.5 |
| 12 | Kotlin | Regex/pattern | ✅ | ✅ | l | 16 | — |
| 13 | C | Regex/pattern | ✅ | ✅ | m | 16 | — |
| 14 | Bash | Regex/pattern | ✅ | ✅ | n | 16 | PowerShell 5.1 (with translator) |
| 15 | Perl | Regex/pattern | ✅ | ✅ | o | 16 | Strawberry Perl 5.42.0 |
| 16 | PHP | Regex/pattern | ✅ | ⛔ Removed | — | — | — |
| 17 | Lua | Regex/pattern | ✅ | ⛔ Removed | — | — | — |
| 18 | Scala | Regex/pattern | ✅ | ⛔ Removed | — | — | — |
| 19 | SQL | Regex/pattern | ✅ | — | — | — | — |

*Languages 16–18 retain full parsing and generation support but were removed from the execution matrix. Their `LanguageID` values remain permanently assigned in the registry.*

## Appendix C: Ledger Event Type Taxonomy

```
Session Lifecycle        Node Mutations             Connection Events
├── SESSION_CREATED      ├── NODE_CREATED           ├── CONNECTION_CREATED
└── SESSION_CLOSED       ├── NODE_DELETED           └── CONNECTION_DELETED
                         ├── NODE_MOVED
Import Events            ├── NODE_CODE_EDITED       Export Events
├── FILE_IMPORTED        ├── NODE_PARAMS_CHANGED    ├── EXPORT_STARTED
└── REPOSITORY_IMPORTED  ├── NODE_LANGUAGE_CHANGED  └── EXPORT_COMPLETED
                         ├── NODE_TYPE_CHANGED
Execution Events         └── NODE_IO_CHANGED        Conversion Events
├── NODE_EXECUTED                                   ├── LANGUAGE_CONVERSION
└── EXECUTION_BATCH                                 └── BULK_CONVERSION
```

## Appendix D: API Surface Summary

### Core APIs (app.py)

| Prefix | Endpoints | Purpose |
|--------|-----------|---------|
| `/api/canvas/` | ~20 | Node CRUD, position, connections |
| `/api/palette/` | ~10 | Component search, categories, custom nodes |
| `/api/ast-grep/` | ~5 | Structural code search and refactoring |
| `/api/paradigm/` | ~15 | Paradigm switching, element management |
| `/api/repository/` | ~15 | File/repo import with dependency strategy |
| `/api/uir/` | ~30 | Translation, conversion, batch operations |
| `/api/ledger/` | ~5 | Session history, node lineage |
| `/api/ai/` | ~3 | AI assistant integration |
| `/api/export/` | ~35 | Multi-language code export |

### Runtime APIs (runtime.py)

| Prefix | Endpoints | Purpose |
|--------|-----------|---------|
| `/api/engines` | 1 | Engine manifest — single source of truth |
| `/api/engines/available` | 1 | Available engine listing |
| `/api/registry/` | 22 | Matrix status, slot operations, commit, permissions |
| `/api/execution/ledger/` | 6 | REPL-style execution, namespace management |
| `/api/execution/engines/` | 2 | Multi-engine and simultaneous execution |
| `/api/execution/multi-debug/` | 7 | Concurrent debug sessions |
| `/api/projects/` | 4 | Project persistence (save/load/list/delete) |
| `/api/demos/` | 2 | Engine demo tab content |
| `/api/runtime/` | 3 | Server control, status, info |

---

## References

- Brunsfeld, M. (2018). Tree-sitter: An incremental parsing system for programming tools. GitHub.
- Ellis, C. A., & Gibbs, S. J. (1989). Concurrency control in groupware systems. ACM SIGMOD Record.
- Haan, R., & Nadi, S. (2019). Comby: A tool for structural code search and replace. ICSE Demo.
- Haas, A., et al. (2017). Bringing the web up to speed with WebAssembly. PLDI.
- Herrington, H. (2022). ast-grep: A CLI tool for code structural search, lint, and rewriting. GitHub.
- Kreps, J., et al. (2011). Kafka: A distributed messaging system for log processing. NetDB Workshop.
- Lattner, C., & Adve, V. (2004). LLVM: A compilation framework for lifelong program analysis & transformation. CGO.
- Pasternak, E., et al. (2017). Tips for creating a block language with Blockly. IEEE Blocks and Beyond.
- Patterson, D. A., & Hennessy, J. L. (2013). Computer Organization and Design: The Hardware/Software Interface (5th ed.). Morgan Kaufmann.
- Resnick, M., et al. (2009). Scratch: Programming for all. Communications of the ACM.
- Shapiro, M., et al. (2011). Conflict-free replicated data types. SSS.
- Torvalds, L. (2005). Git: Fast version control system. git-scm.com.
- Würthinger, T., et al. (2013). One VM to rule them all. Onward!
