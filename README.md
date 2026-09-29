# Nexus — Code Intelligence & Impact Analysis Platform

Milestone 4 adds **PostgreSQL persistence via SQLAlchemy** over the FastAPI layer.

It answers a practical question:

> If this function, class, or file changes, what else in the repository is *potentially affected*?

There is no frontend or AI in this milestone. It uses PostgreSQL (or SQLite for local dev) via SQLAlchemy for persistence.

## What is implemented

- Repository scanner (local `.py` files, nested packages)
- Python AST parsing
- FILE, FUNCTION, and CLASS entities (including methods)
- Relationships: `CONTAINS`, `IMPORTS`, `CALLS`, `INSTANTIATES`
- Simple local import and call resolution (including aliases, `self.method()`, constructors, and `obj.method()`)
- Adjacency-list dependency graph (forward and reverse)
- DFS/BFS traversal with a visited set (cycles are safe)
- Impact analysis built on graph traversal
- CLI entry point

## Run

```bash
python -m app.cli examples/sample_project
python -m app.cli examples/realistic_project
python -m pytest
```


## API Server

The API runs locally using FastAPI. Data is persisted to a database (defaulting to a local SQLite database for zero-config development, but supports PostgreSQL).

### Install dependencies
```bash
pip install -r requirements.txt
```

### Start the server
```bash
python -m uvicorn app.main:app --reload
```


### Configuration
Configure the database via the `DATABASE_URL` environment variable:
```bash
# SQLite (default)
export DATABASE_URL="sqlite:///./nexus.db"

# PostgreSQL
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/nexus"
```

### Endpoints

**Check Health:**
```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

**Analyze a Repository:**
*Note: Currently only supports local filesystem paths. Future versions will include repository ingestion mechanisms.*
```bash
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"repository_path": "examples/sample_project"}'
# {"analysis_id": "...", "repository_path": "...", "total_entities": 8, "total_relationships": 10, "status": "success"}
```

**Retrieve Entities:**
```bash
curl http://localhost:8000/analysis/<analysis_id>/entities
```

**Retrieve Impact Analysis:**
```bash
curl "http://localhost:8000/analysis/<analysis_id>/impact?entity_id=function:examples/sample_project/payment.py:process_payment:3"
```

Automatic interactive documentation is available at `http://localhost:8000/docs` while the server is running.

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

Static resolution is intentionally simple. Unresolved cases include relative imports, dynamic calls, highly ambiguous method calls on untyped instances, chained attributes, and third-party / stdlib modules.

See [NEXUS_NOTES.md](NEXUS_NOTES.md) for graph representation, relationship rules, and a fuller limitation list.
