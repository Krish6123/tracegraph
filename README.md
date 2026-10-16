# Nexus — Code Intelligence & Impact Analysis Platform

Milestone 5 adds **Git-Aware Impact Analysis**.

It answers a practical question:

> If this function, class, or file changes, what else in the repository is *potentially affected*?

There is no frontend or AI in this milestone. It uses PostgreSQL (or SQLite for local dev) via SQLAlchemy for persistence, and now integrates tightly with the local Git CLI to map working tree and commit changes to the baseline analysis graph.

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

**Retrieve Git-Aware Impact Analysis:**
```bash
curl -X POST http://localhost:8000/analysis/<analysis_id>/git-impact -H "Content-Type: application/json" -d '{}'
```

Automatic interactive documentation is available at `http://localhost:8000/docs` while the server is running.

## Frontend dashboard (M6)

The React + TypeScript dashboard lives in `frontend/` and uses the existing FastAPI endpoints. It does not change the deterministic analysis engine. The repository path entered in the browser must be accessible to the machine running FastAPI; the browser does not upload source files.

Start the API in one terminal:
```bash
python -m uvicorn app.main:app --reload
```

Start the dashboard in another terminal:
```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal. During development, Vite proxies `/api` requests to `http://127.0.0.1:8000` and removes the `/api` prefix before forwarding them. To use a different API origin, set `VITE_API_BASE_URL` to that origin and configure it to accept the `/api` prefix (or provide equivalent reverse-proxy routing). A production host must serve the built dashboard and route its API requests to FastAPI under the same origin.

The dashboard includes repository analysis, an overview, a direct-neighbor dependency graph, entity impact reports, and Git-aware changed-file impact. Git comparisons use the baseline commit saved with the analysis by default and otherwise support optional base and target refs.

## Architecture

```
repository scanner   <----   (Local Git CLI integration)
        ↓                            |
Python AST parser                    |
        ↓                            |
entities + relationships             |
        ↓                            |
dependency graph                     |
        ↓                            |
impact analysis     <----------------+
        ↓
API / CLI
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

## Python package analysis

Nexus scans nested Python directories and records repository-relative paths. It infers package names from directories containing `__init__.py` and module names from the file tree. For example, `services/payment_service.py` maps to `services.payment_service`. The scanner parses source with Python's `ast` module; it never executes the analyzed repository.

Classes remain `CLASS` entities. Methods remain `FUNCTION` entities with qualified names such as `PaymentService.process`. `CONTAINS` edges represent file-to-class, class-to-method, and file-to-top-level-function structure.

Imports are connected only when a module or symbol maps to a file/entity in the scanned repository. Simple aliases are tracked. Calls resolve same-file/imported functions, module attributes, `self.method()`, class-qualified calls, and object methods when the object is bound to a local class constructor. Constructor use is represented with `INSTANTIATES`; method invocation remains `CALLS`. Unknown or ambiguous receivers are omitted and may be listed as unresolved.

This is static analysis: Nexus does not execute the analyzed code and does not perform complete Python type inference. Relative and dynamic imports, inheritance and dynamic dispatch, and untyped ambiguous method calls are outside the supported resolution rules. When Nexus cannot determine one local target from the available syntax and repository files, it leaves the relationship unresolved instead of guessing.
