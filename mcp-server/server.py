from mcp.server.fastmcp import FastMCP
import os
import json
import uuid
import kuzu
import shutil

# Initialize FastMCP
mcp = FastMCP("PersonalCRM-Kuzu", host="0.0.0.0")

# Database Path
DB_PATH = os.getenv("KUZU_PATH", "/app/kuzu_data/personal_crm_db")

# Initialize KuzuDB


def get_db():
    return kuzu.Database(DB_PATH)


def get_conn(db=None):
    if db is None:
        db = get_db()
    return kuzu.Connection(db)


def get_schema_info(conn):
    """Get list of tables from schema."""
    # CALL db.schema() returns name, type, properties
    # The output format depends on Kuzu version.
    # For 0.4.0+, usually generic query result.
    try:
        # We use a try-except block to handle potential schema fetch issues
        # Ideally we parse the result.
        # For this POC, we just return a list of dicts if possible.
        return []  # Placeholder if schema query is complex to parse without running it
    except Exception as e:
        print(f"Error fetching schema: {e}")
        return []


def initialize_schema():
    """Initialize the KuzuDB schema for Person, Rules, and base structures."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    db = get_db()
    conn = kuzu.Connection(db)

    # Kuzu doesn't support IF NOT EXISTS for tables in all versions.
    # We try to create and catch error if exists.
    try:
        conn.execute(
            "CREATE NODE TABLE Person(uuid STRING, name STRING, data STRING, PRIMARY KEY (uuid))"
        )
        print("Initialized Person table.")
    except RuntimeError as e:
        if "already exists" in str(e):
            pass
        else:
            print(f"Note: Person table creation skipped/failed: {e}")

    try:
        conn.execute(
            "CREATE NODE TABLE Rule(name STRING, cypher STRING, description STRING, PRIMARY KEY (name))"
        )
        print("Initialized Rule table.")
    except RuntimeError as e:
        if "already exists" in str(e):
            pass
        else:
            print(f"Note: Rule table creation skipped/failed: {e}")


def ensure_rel_table(conn, rel_type: str):
    """Ensure a relationship table exists."""
    safe_type = "".join(c for c in rel_type if c.isalnum() or c == "_")
    if not safe_type:
        raise ValueError("Invalid relationship type")

    try:
        conn.execute(
            f"CREATE REL TABLE {safe_type}(FROM Person TO Person, data STRING)"
        )
        print(f"Created relationship table {safe_type}")
    except RuntimeError as e:
        if "already exists" in str(e):
            pass
        else:
            # If it fails for another reason, raise
            raise e
    return safe_type


@mcp.tool()
def add_person(name: str, properties: str = "{}") -> str:
    """
    Add a new person with arbitrary properties.
    Args:
        name: Name of the person.
        properties: JSON string of properties (e.g., '{"gender": "M", "job": "Engineer"}')
    """
    try:
        props = json.loads(properties)
    except json.JSONDecodeError:
        return "Error: properties must be a valid JSON string."

    pid = str(uuid.uuid4())
    conn = get_conn()

    # Check if name exists (enforce unique name for this POC)
    res = conn.execute("MATCH (p:Person) WHERE p.name = $name RETURN p", {"name": name})
    if res.has_next():
        return f"Error: Person with name '{name}' already exists."

    conn.execute(
        "CREATE (p:Person {uuid: $uuid, name: $name, data: $data})",
        {"uuid": pid, "name": name, "data": properties},
    )
    return f"Added person: {name} ({pid})"


@mcp.tool()
def add_fact(from_name: str, to_name: str, type: str, properties: str = "{}") -> str:
    """
    Add a relationship/fact between two people.
    Args:
        from_name: Name of the subject person.
        to_name: Name of the object person.
        type: Type of relation (e.g., 'parent_child', 'spouse', 'met_at').
        properties: JSON string of details.
    """
    try:
        json.loads(properties)
    except json.JSONDecodeError:
        return "Error: properties must be a valid JSON string."

    conn = get_conn()
    try:
        safe_type = ensure_rel_table(conn, type)
    except ValueError:
        return "Error: Invalid relationship type name."

    # Check existence
    res_from = conn.execute(
        "MATCH (p:Person) WHERE p.name = $name RETURN p.uuid", {"name": from_name}
    )
    if not res_from.has_next():
        return f"Error: Person '{from_name}' not found."

    res_to = conn.execute(
        "MATCH (p:Person) WHERE p.name = $name RETURN p.uuid", {"name": to_name}
    )
    if not res_to.has_next():
        return f"Error: Person '{to_name}' not found."

    # Create relationship
    query = f"MATCH (a:Person {{name: $from_name}}), (b:Person {{name: $to_name}}) CREATE (a)-[:{safe_type} {{data: $data}}]->(b)"
    conn.execute(
        query, {"from_name": from_name, "to_name": to_name, "data": properties}
    )

    return f"Added fact: {from_name} --[{safe_type}]--> {to_name}"


@mcp.tool()
def add_rule(name: str, cypher_query: str, description: str = "") -> str:
    """
    Save a reusable Cypher query/rule.
    Args:
        name: Unique name for the rule (e.g., 'find_siblings').
        cypher_query: The Cypher query string. Use parameters like $name if needed.
        description: Optional description.
    """
    conn = get_conn()
    # Upsert rule
    # Kuzu MERGE simple upsert
    try:
        conn.execute(
            "MERGE (r:Rule {name: $name}) SET r.cypher = $cypher, r.description = $desc",
            {"name": name, "cypher": cypher_query, "desc": description},
        )
        return f"Rule '{name}' saved."
    except Exception as e:
        return f"Error saving rule: {e}"


@mcp.tool()
def get_rule(name: str) -> str:
    """Retrieve a stored rule's Cypher query."""
    conn = get_conn()
    res = conn.execute(
        "MATCH (r:Rule) WHERE r.name = $name RETURN r.cypher, r.description",
        {"name": name},
    )
    if res.has_next():
        row = res.get_next()
        return f"Rule: {name}\nDescription: {row[1]}\nCypher: {row[0]}"
    return "Rule not found."


@mcp.tool()
def list_rules() -> str:
    """List all stored rules."""
    conn = get_conn()
    res = conn.execute("MATCH (r:Rule) RETURN r.name, r.description")
    rules = []
    while res.has_next():
        row = res.get_next()
        # Kuzu row might be list or dict depending on driver version.
        # Assuming list for now based on older docs, but let's be safe.
        r_name = row[0] if isinstance(row, list) else row["r.name"]
        r_desc = row[1] if isinstance(row, list) else row["r.description"]
        rules.append(f"- {r_name}: {r_desc}")
    return "\n".join(rules) if rules else "No rules found."


@mcp.tool()
def run_cypher(query: str) -> str:
    """
    Execute a raw Cypher query.
    Args:
        query: Cypher query string.
    """
    conn = get_conn()
    try:
        result = conn.execute(query)
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append(str(row))
        return "\n".join(rows) if rows else "No results."
    except Exception as e:
        return f"Error executing query: {str(e)}"


@mcp.tool()
def list_relation_types() -> str:
    """List all relationship types (Edge Tables)."""
    conn = get_conn()
    try:
        # Use SHOW TABLES since db.schema() is deprecated/removed in newer Kuzu versions
        result = conn.execute("CALL SHOW_TABLES() RETURN *")
        tables = []
        while result.has_next():
            row = result.get_next()
            # row format: [id, name, type, storage, options] or similar depending on version
            # We want to filter for type='REL'
            # Let's inspect the row structure based on previous manual query result:
            # [3, 'created', 'REL', 'local(kuzu)', '']
            if isinstance(row, list) and len(row) >= 3:
                if row[2] == "REL":
                    tables.append(row[1])
            elif isinstance(row, dict) and row.get("type") == "REL":
                tables.append(row.get("name"))

        return "\n".join(tables) if tables else "No relationship types found."
    except Exception as e:
        return f"Could not list types: {e}"


@mcp.tool()
def inspect_person_schema() -> str:
    """Return a sample of people data."""
    conn = get_conn()
    try:
        result = conn.execute("MATCH (p:Person) RETURN p.name, p.data LIMIT 5")
        output = []
        while result.has_next():
            row = result.get_next()
            output.append(str(row))
        return "\n".join(output) if output else "No people found."
    except Exception as e:
        return f"Error: {e}"


# Run initialization
try:
    initialize_schema()
except Exception as e:
    print(f"Initialization warning: {e}")

# SSE App
app = mcp.sse_app()

if __name__ == "__main__":
    mcp.run()
