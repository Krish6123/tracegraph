# Nexus notes — Milestone 4

This document describes the deterministic static-analysis engine. It is written so the design can be explained in an interview without extra libraries or hidden magic.

## Implemented

- Scan a local directory for Python files (including nested packages and `__init__.py`)
- Parse each file with the standard-library `ast` module
- Extract FILE, FUNCTION, and CLASS entities (including methods)
- Give every entity a unique stable string ID
- Extract CONTAINS, IMPORTS, CALLS, and INSTANTIATES relationships
- Resolve simple local imports, module imports, and import aliases
- Resolve simple method calls (`self.method()`, `obj.method()`) and class constructors
- Build an adjacency-list graph with forward and reverse indexes
- Traverse with DFS or BFS using a visited set
- Report potential impact of changing a selected entity
- CLI: `python -m app.cli <repository_path>`

Not in this milestone: AI/LLM, frontend, Docker, Redis, NetworkX, authentication, GitHub OAuth, multi-language support.


## API Layer
A thin FastAPI layer is implemented over the deterministic engine.
- Routing logic converts HTTP requests into internal engine logic.
- Persistence is handled via SQLAlchemy (using `psycopg` for PostgreSQL and native `sqlite3` for local testing/dev).
- The `DATABASE_URL` environment variable drives connections.
- During impact analysis, the DB objects are hydrated back into a `DependencyGraph` in-memory. This prevents tightly coupling the complex pathfinding logic to SQL CTEs, remaining easily explainable.
- `Entity.entity_id` values (e.g. `file:main.py`) are strictly preserved. Internal DB `id` integers act only as surrogate primary keys.

## Architecture

```
find_python_files(path)
        → parse_python_file (ast.parse)
        → extract FILE / FUNCTION / CLASS
        → resolve local imports and calls
        → DependencyGraph.add_node / add_edge
        → traverse forward + reverse
        → ImpactReport
```

The orchestrator is `app.analysis.engine.analyze_repository`.

## Entity IDs

IDs are strings derived from path and location, not scan-order integers.

| Kind     | ID shape                                      |
|----------|-----------------------------------------------|
| file     | `file:{relative/path.py}`                     |
| function | `function:{relative/path.py}:{name}:{lineno}` |
| class    | `class:{relative/path.py}:{name}:{lineno}`    |

The same repository always produces the same IDs. Duplicates are avoided by storing entities in a dict keyed by ID.

Paths are stored as posix-style repository-relative paths so Windows and Unix scans match.

## Graph representation

`DependencyGraph` is an adjacency list:

- `_nodes`: id → `Entity`
- `_forward`: id → list of `(target_id, relationship_type)`
- `_reverse`: id → list of `(source_id, relationship_type)`
- `_edges`: list of `Relationship`

Operations: `add_node`, `add_edge`, `nodes`, `edges`, `get_node`, `forward_neighbors`, `reverse_neighbors`, `forward_graph`, `reverse_graph`.

Traversal (`traverse`) supports `direction="forward"|"reverse"` and `algorithm="dfs"|"bfs"`. A `visited` set is marked **before** walking neighbors so a cycle cannot recurse forever.

## Supported relationships

| Type         | Direction              | Meaning |
|--------------|------------------------|---------|
| CONTAINS     | file/class → func/class| The file or class defines that entity |
| IMPORTS      | file → file            | A local module import resolved to a repository file |
| CALLS        | function → function    | A statically resolved call |
| INSTANTIATES | function → class       | A statically resolved class constructor call |

## Import resolution

Resolved when the imported module maps to a `.py` file in the same repository:

```python
from payment import process_payment
import payment
from orders import create_order
```

`import payment as p` binds `p` to the payment file. `from payment import process_payment as pay` binds `pay` to the function.

Stdlib and third-party modules have no matching file, so they produce no IMPORTS edge.

## Call resolution

Resolved when the callee can be determined from the current file plus import bindings:

```python
process_payment()           # imported name or same-file function
create_order()
payment.process_payment()   # import payment; attribute of that module
```

The enclosing function is tracked with an AST visitor (function stack). Module-level calls are ignored because CALLS is defined as function → function.

## Impact analysis

Given a selected entity, the report lists:

- selected entity
- **direct dependencies** — forward neighbors (what it uses)
- **indirect dependencies** — forward reachable minus direct
- **direct dependents / callers** — reverse neighbors (what uses it)
- **indirect dependents / callers** — reverse reachable minus direct

Wording is **potentially affected**. This is static structure, not a proof that production will break.

CONTAINS edges are part of the same graph, so a function’s containing file appears as a reverse neighbor. That is deliberate: changing a function potentially affects the file that holds it.

## Examples

Sample project call chain:

```
main() → create_order() → process_payment() → save_transaction()
```

Impact of `process_payment`:

- direct dependency: `save_transaction`
- direct dependent: `create_order` (and the containing `payment.py` file via CONTAINS)
- indirect dependent: `main` (via `create_order`)

CLI:

```bash
python -m app.cli examples/sample_project
```

## Known limitations

Static analysis cannot recover everything Python can do at runtime. Unresolved or out of scope:

- Relative imports (`from .payment import process_payment`)
- Dynamic imports (`__import__`, `importlib`)
- Dynamic calls (`getattr`, callbacks, function arguments)
- Attribute chains longer than `module.func` (`pkg.mod.func()`)
- Highly ambiguous method calls on untyped instances (if multiple classes could match `obj.save()`, the edge is omitted)
- Overloaded / duplicate names in one file (the earliest line is used)
- Star imports from non-local modules
- Control-flow sensitivity (a call inside `if False` still counts)
- Multiple languages, type stubs, or C extensions

When resolution is ambiguous, Nexus **omits** the edge rather than guessing.

## Tests

```bash
python -m pytest
```

Coverage includes scanner path errors, entity extraction, classes/functions, imports, calls, graph nodes/edges, reverse graph, DFS/BFS, direct vs indirect dependencies, impact analysis, and cyclic dependencies.

## Git-Aware Impact (M5)

- Uses local `git` CLI via `subprocess`.
- Granularity is at the file level: changing one function in a file causes the system to map the entire file (all entities within it) as "changed," thereby flagging dependents of *all* functions in that file as potentially affected.
- Untracked new files are detected as ADDED but result in zero baseline impact (no baseline dependents).
- Diffs against uncommitted working tree changes by default unless a `target_ref` is supplied.
- Analysis baseline commit is recorded via `commit_hash` in `AnalysisRecord`.
