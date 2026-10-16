# Tracegraph — Codebase Intelligence & Change Impact Analysis

> A deterministic static-analysis engine and developer dashboard that maps Python repositories into entity-relationship graphs to trace dependencies and evaluate change blast radius.

---

### The Problem

> *When code changes, which other parts of the repository might be affected?*

Refactoring a shared function, altering a method signature, or renaming a class often triggers subtle downstream regressions. Developers typically rely on mental models, grep searches, or trial-and-error test runs to guess what might break.

**Tracegraph** provides an automated, deterministic answer. It parses Python source code into abstract syntax trees without executing it, extracts code entities and their connections, constructs an in-memory dependency graph, and walks forward and reverse paths to reveal the potential blast radius of any modification—from a single function to an entire Git working tree diff.

---

## Architecture

Tracegraph separates deterministic AST parsing, graph pathfinding, relational persistence, and visual exploration into clean, decoupled layers:

```mermaid
flowchart TD
    subgraph Ingestion["1. Repository Ingestion"]
        Repo[("Python Source Files\n*.py")] --> Scanner["Scanner & Package Discovery\napp.scanner"]
        Scanner --> Parser["AST Parser & Symbol Extractor\napp.parser"]
    end

    subgraph Extraction["2. Graph Construction"]
        Parser --> Entities["Entities\nFILE · CLASS · FUNCTION"]
        Parser --> Relations["Relationships\nCONTAINS · IMPORTS · CALLS · INSTANTIATES"]
        Entities --> Graph["In-Memory DependencyGraph\nForward & Reverse Adjacency Lists"]
        Relations --> Graph
    end

    subgraph Persistence["3. Database Layer"]
        Entities -.-> DB[("Database\nSQLite (nexus.db) / PostgreSQL")]
        Relations -.-> DB
        Migrations["Safe Schema Migrations\napp.db.migrations"] --> DB
    end

    subgraph Analysis["4. Intelligence & Diff Engines"]
        Graph --> ImpactEngine["Impact Engine\nTransitive DFS/BFS Traversal"]
        GitCLI["Local Git CLI\nprovider.py"] --> GitEngine["Git-Aware Impact Engine\napp.analysis.git_impact"]
        Graph --> GitEngine
        DB -. Hydrate .-> Graph
    end

    subgraph Interfaces["5. Delivery"]
        ImpactEngine --> FastAPI["FastAPI REST API\napp.api"]
        GitEngine --> FastAPI
        FastAPI --> Dashboard["React + TypeScript Dashboard\nfrontend/ (Vite)"]
        ImpactEngine --> CLI["CLI Tool\napp.cli"]
    end
```

---

## Core Capabilities

### 1. Deterministic AST Static Analysis
Tracegraph inspects source files using Python's built-in `ast` module. It never executes or imports target code, avoiding arbitrary code execution vulnerabilities and runtime dependency issues.
- **Package & Module Discovery:** Identifies nested packages via directory traversal and `__init__.py` markers.
- **Deterministic Entity Identifiers:** Every entity receives a deterministic string ID derived from its repository-relative POSIX path and AST line number (note that moving code within a file updates the line number in that ID):
  - File: `file:services/payment.py`
  - Class: `class:services/payment.py:PaymentGateway:14`
  - Function / Method: `function:services/payment.py:process_payment:42`

### 2. Relationship Extraction
The AST visitor resolves four core structural relationships:
- `CONTAINS` — A file or class defines a child class or function/method.
- `IMPORTS` — A module imports another module or symbol located within the repository.
- `CALLS` — A function calls another statically resolvable function or method (including `self.method()`, module-qualified calls, and class methods).
- `INSTANTIATES` — A function instantiates a known class constructor.

When symbol resolution is ambiguous or dynamic, Tracegraph intentionally omits the edge rather than guessing.

### 3. Bidirectional Dependency Graph & Impact Engine
Entities and relationships populate an adjacency-list `DependencyGraph` maintaining both forward and reverse indices.
- **Forward Traversal:** Discovers what an entity uses (direct and transitive dependencies).
- **Reverse Traversal:** Discovers what uses an entity (direct callers, enclosing containers, and indirect dependents).
- **Cycle Safety:** Traversal algorithms (DFS and BFS) track visited sets prior to walking neighbors, terminating cleanly on circular imports or recursive calls.
- **Blast Radius Classification:** Categorizes affected entities into direct dependencies, indirect dependencies, direct dependents, and indirect dependents.

### 4. Git-Aware Impact Analysis
Connects the dependency graph to your version control workflow:
- **Baseline Capture:** When the analyzed repository is under Git version control with existing commits, Tracegraph automatically records the current commit (`HEAD`) as the analysis baseline `commit_hash`. (If an unversioned folder or repo without commits is analyzed, the baseline hash is stored as `null`.)
- **Accurate Diff Mapping:** Compares uncommitted working tree changes (or an explicit Git ref) against the baseline using local Git CLI plumbing (`git diff --name-status`):
  - **Modified** and **deleted** files map all entities defined in those baseline file paths.
  - **Renamed** files map baseline entities using their previous path (`old_path`).
  - **Added** files are listed in detected changes, but map to zero baseline entities since they did not exist in the baseline analysis.
- **Downstream Impact:** Traverses reverse dependencies from all mapped baseline entities to determine which existing parts of the codebase are potentially affected by the changes.

### 5. Interactive Web Dashboard
A modern React + TypeScript single-page application built on Vite:
- **Repository:** Run on-demand scans on local directories.
- **Overview:** High-level metrics, package structures, entity counts, baseline commit info, and parse issue diagnostics.
- **Dependency Graph:** Interactive SVG visualization of direct neighbors for any chosen entity.
- **Impact Analysis:** Detailed inspection of upstream and downstream dependents with entity filtering.
- **Git Changes:** Real-time diffing against the saved baseline commit (or user-provided refs), presenting a changed-files list alongside mapped baseline entities and potentially affected dependents.

---

## Quickstart (Windows PowerShell)

### Prerequisites
- **Python 3.10+** (with `pip` and `venv`)
- **Node.js 18+** (with `npm`)
- **Git** installed and available on `PATH`

### 1. Backend Setup

From the repository root in PowerShell:

```powershell
# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Start the FastAPI server with reload
python -m uvicorn app.main:app --reload
```

The API will start at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### 2. Frontend Setup

In a second PowerShell terminal:

```powershell
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

Open `http://localhost:5173` in your browser. During development, Vite automatically proxies `/api` requests to `http://127.0.0.1:8000`.

---

## Configuration & Persistence

Tracegraph uses **SQLAlchemy 2.0** for persistence.

### Database Settings
By default, Tracegraph creates and uses a local SQLite database (`nexus.db`) in the repository root for zero-config local development. To use PostgreSQL instead, configure the `DATABASE_URL` environment variable:

```powershell
# PowerShell syntax
$env:DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/tracegraph"
```

### Automatic Schema Migrations
Tracegraph includes a built-in, lightweight schema migration runner (`app.db.migrations`). When FastAPI starts, `init_db()` inspects existing tables and applies non-destructive incremental updates (such as adding the `commit_hash` column to existing analysis tables) while strictly preserving pre-existing analysis records, entities, and relationships.

---

## CLI Usage

For quick terminal-based analysis without launching the web server:

```powershell
# Analyze an example project
python -m app.cli examples/sample_project

# Analyze a realistic multi-package project
python -m app.cli examples/realistic_project
```

The CLI outputs discovered packages, discovered Python files, syntax parse errors (if any), code entities, individual resolved relationships, a graph node/edge summary, and an example impact analysis report.

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | API health check status |
| `POST` | `/analyze` | Scan and analyze a repository on the local filesystem |
| `GET` | `/analysis/{id}` | Retrieve analysis summary, status, and parse errors |
| `GET` | `/analysis/{id}/entities` | List all discovered entities (files, classes, functions) |
| `GET` | `/analysis/{id}/relationships` | List all resolved dependency edges |
| `GET` | `/analysis/{id}/impact?entity_id=...` | Calculate direct and transitive blast radius for an entity |
| `POST` | `/analysis/{id}/git-impact` | Diff working tree or Git refs against the analysis baseline |

### Example cURL Commands (Bash / Command Line)

```bash
# 1. Run analysis on a repository
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repository_path": "examples/sample_project"}'

# 2. Query impact for a specific function
curl "http://localhost:8000/analysis/<ANALYSIS_ID>/impact?entity_id=function:examples/sample_project/payment.py:process_payment:3"

# 3. Compare working tree changes against the saved baseline
curl -X POST http://localhost:8000/analysis/<ANALYSIS_ID>/git-impact \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Testing & Production Builds

### Running Python Tests
The test suite validates parser extraction, import resolution, graph traversal, cycle handling, database migrations, and Git-impact analysis. Run pytest from the repository root:

```powershell
# From the repository root
.\.venv\Scripts\python.exe -m pytest
```

### Building the Frontend
To build the production bundle with TypeScript type-checking and Vite bundling, run the build command inside the `frontend/` directory:

```powershell
# Inside frontend/
cd frontend
npm run build
```

The compiled assets are output to `frontend/dist/`.

---

## Technical Scope & Limitations

Tracegraph is designed around deterministic static analysis. It provides structural awareness of potential impact, not a formal proof that runtime behavior will fail.

### What Tracegraph Resolves
- Local module and package imports with absolute repository mappings
- Simple import aliases (`import payment as p`, `from module import func as f`)
- Function calls within the same module or imported from local modules
- Method invocations via `self.method()`, class constructors, and direct instance calls
- Cycles in call graphs and import graphs without recursion errors

### Intentional Constraints
- **Static Resolution Only:** Tracegraph never executes runtime code. Dynamic imports (`__import__`, `importlib`), reflection (`getattr`, `setattr`), and runtime monkey-patching are not tracked.
- **Ambiguous Method Calls:** Untyped receiver objects with multiple candidates across classes are omitted rather than guessed.
- **Language Scope:** Focused specifically on Python (`.py`) source trees. C-extensions, Cython, and type stub files (`.pyi`) are not currently analyzed.
- **External Dependencies:** Standard library and third-party vendor packages (`site-packages`) are excluded from local graph construction.
