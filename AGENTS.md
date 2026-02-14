# AGENTS.md - Personal CRM Core

This file provides context, guidelines, and commands for AI agents operating in the `personal-crm-core` repository.

## 1. Project Context
**Personal CRM Core** is a graph-based personal relationship management system.
- **Backend**: CozoDB (Hybrid Relational/Graph/Vector database).
- **Interface**: Model Context Protocol (MCP) server used by AI agents.
- **Philosophy**: Dynamic schema (JSON properties) + Dynamic logic (Datalog rules) + Fact-based relationships.

## 2. Environment & Build

### Directory Structure
- `mcp-server/`: Python application implementing the MCP server.
- `cozo/`: Database schema and initial Datalog scripts.
- `docker-compose.yml`: Infrastructure orchestration (CozoDB instance).

### Setup & Run
1.  **Prerequisites**: Python 3.10+, Docker.
2.  **Install Dependencies**:
    ```bash
    pip install -r mcp-server/requirements.txt
    ```
3.  **Start Infrastructure**:
    ```bash
    docker-compose up -d
    ```
4.  **Run MCP Server**:
    ```bash
    # Set environment variables if needed (COZO_HOST, COZO_AUTH_TOKEN)
    python mcp-server/server.py
    ```

### Testing
*Currently, no automated test suite exists. Agents should implement tests using `pytest`.*
- **Recommended Test Command**:
    ```bash
    pytest tests/
    ```
- **Single Test**:
    ```bash
    pytest tests/test_file.py::test_function
    ```

## 3. Code Style & Guidelines

### Python
- **Formatter**: Follow `black` style (88 char line limit).
- **Type Hints**: **MANDATORY** for all function signatures.
    ```python
    def add_person(name: str, properties: str = "{}") -> str:
    ```
- **Docstrings**: Required for all tools. Use Google-style or clear description + Args + Returns.
- **Imports**:
    1.  Standard Library (`os`, `json`, `uuid`)
    2.  Third Party (`requests`, `mcp`)
    3.  Local Imports
- **Error Handling**:
    -   Catch specific exceptions (`requests.exceptions.RequestException`).
    -   Return descriptive error strings for MCP tools, do not crash the server.
    -   Check JSON validity before parsing:
        ```python
        try:
            data = json.loads(properties)
        except json.JSONDecodeError:
            return "Error: Invalid JSON"
        ```

### Datalog / CozoDB
- **Read-Before-Write**: ALWAYS check existing patterns before adding new keys.
    -   Use `list_relation_types()` to find existing edge types (e.g., `parent_child`).
    -   Use `inspect_person_schema()` to find existing property keys (e.g., `job` vs `occupation`).
- **Schema**:
    -   **Person**: `person {id, name, data}`. `data` is arbitrary JSON.
    -   **Fact**: `fact {from_id, to_id, type, data}`. `type` defines the edge.
    -   **Rule**: `rule {name, body}`. Persistent logic.
- **Querying**:
    -   Prefer `run_custom_query` to utilize stored rules.
    -   Use `?[var]` syntax for outputs.
    -   Use `*table` to access stored tables, regular names for derived rules.

## 4. Agent Protocols
- **Consistency**: Do not invent new relation types if a semantic equivalent exists.
- **Atomic Operations**: When adding complex data, resolve IDs first, then insert.
- **Safety**: Verify Datalog syntax before execution.
- **Logging**: The server uses standard output; keep logs clean.

## 5. Deployment
- Docker containerization is the primary deployment method.
- Ensure `requirements.txt` is pinned and up to date.

---
*Generated for AI Agent usage. Keep this file updated as the project evolves.*
