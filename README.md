# Nexus — Code Intelligence & Impact Analysis Platform

Milestone 1 is a **deterministic static-analysis engine** for local Python repositories.

It answers a practical question:

> If this function, class, or file changes, what else in the repository is *potentially affected*?

There is no AI, API server, database, or UI in this milestone.

## What is implemented

- Repository scanner (local `.py` files)
- Python AST parsing
- FILE, FUNCTION, and CLASS entities with stable IDs
- Relationships: `CONTAINS`, `IMPORTS`, `CALLS`
- Simple local import and call resolution
- Adjacency-list dependency graph (forward and reverse)
- DFS/BFS traversal with a visited set (cycles are safe)
- Impact analysis built on graph traversal
- CLI entry point

## Run

```bash
python -m app.cli examples/sample_project
python -m pytest
```

## Architecture

```
repository scanner
        ↓
Python AST parser
        ↓
entities + relationships
        ↓
dependency graph
        ↓
impact analysis
        ↓
CLI
```

## Example

`examples/sample_project` contains a small checkout flow:

- `main.py` calls `create_order`
- `orders.py` calls `process_payment`
- `payment.py` calls `save_transaction`
- `database.py` defines `save_transaction`

Changing `process_payment` **potentially affects** `create_order` immediately, and `main` indirectly.

## Known limitations

Static resolution is intentionally simple. Unresolved cases include relative imports, dynamic calls, `self.method()`, chained attributes, and third-party / stdlib modules.

See [NEXUS_NOTES.md](NEXUS_NOTES.md) for graph representation, relationship rules, and a fuller limitation list.
