from mcp.server.fastmcp import FastMCP
import requests
import os
import json
import uuid

# Configuration
COZO_HOST = os.getenv("COZO_HOST", "http://localhost:9070")
COZO_AUTH_TOKEN = os.getenv("COZO_AUTH_TOKEN", "")

# Initialize FastMCP
mcp = FastMCP("PersonalCRM-Cozo")


def initialize_schema():
    """Initialize the database schema if not already done."""
    schema_path = "/app/schema.cozo"
    if not os.path.exists(schema_path):
        # Fallback for local dev if not in docker
        schema_path = "../cozo/schema.cozo"

    if os.path.exists(schema_path):
        print(f"Loading schema from {schema_path}")
        with open(schema_path, "r") as f:
            schema_script = f.read()

        # Check if person table exists
        check_script = "::columns person"
        result = execute_cozo(check_script)
        if not result.get("ok"):
            print("Schema not found. Initializing...")
            init_result = execute_cozo(schema_script)
            if init_result.get("ok"):
                print("Schema initialized successfully.")
            else:
                print(f"Failed to initialize schema: {init_result.get('message')}")
        else:
            print("Schema already exists.")
    else:
        print("Schema file not found. Skipping initialization.")


def execute_cozo(script: str, params: dict | None = None):
    """Execute a script against CozoDB HTTP API"""
    url = f"{COZO_HOST}/text-query"
    headers = {"Content-Type": "application/json", "x-cozo-auth": COZO_AUTH_TOKEN}
    payload = {"script": script, "params": params or {}}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "message": str(e)}


def get_stored_rules() -> str:
    """Fetch all stored Datalog rules from the database."""
    script = "?[body] := rule(_, body)"
    result = execute_cozo(script)
    if result.get("ok"):
        # Concatenate all rule bodies
        return "\n".join([row[0] for row in result.get("rows", [])])
    return ""


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

    # script = "?[id, name, data] <- [[$id, $name, $data]] :put person {id, name, data}"
    # Note: Cozo requires double braces for escaping if using f-string, but we use params.
    script = """
    ?[id, name, data] <- [[$id, $name, $data]]
    :put person {id, name, data}
    """
    params = {"id": pid, "name": name, "data": props}

    result = execute_cozo(script, params)
    if result.get("ok"):
        return f"Added person: {name} ({pid})"
    return f"Failed to add person: {result.get('message')}"


@mcp.tool()
def add_fact(from_name: str, to_name: str, type: str, properties: str = "{}") -> str:
    """
    Add a relationship/fact between two people.
    Args:
        from_name: Name of the subject person.
        to_name: Name of the object person.
        type: Type of relation (e.g., 'parent_child', 'spouse', 'met_at').
        properties: JSON string of details (e.g., '{"location": "Bar", "year": 2023}').
    """
    try:
        props = json.loads(properties)
    except json.JSONDecodeError:
        return "Error: properties must be a valid JSON string."

    # 1. Resolve names to IDs
    # Note: person table structure is person{id, name, data}
    find_ids_script = "?[id, name] := person(id, name, _)"
    result = execute_cozo(find_ids_script)

    if not result.get("ok"):
        return f"Failed to query database: {result.get('message')}"

    rows = result.get("rows", [])
    from_id = next((r[0] for r in rows if r[1] == from_name), None)
    to_id = next((r[0] for r in rows if r[1] == to_name), None)

    if not from_id or not to_id:
        return f"Could not find both persons: {from_name} (Found: {from_id}), {to_name} (Found: {to_id})"

    # 2. Insert Fact
    script = """
    ?[from_id, to_id, type, data] <- [[$from_id, $to_id, $type, $data]]
    :put fact {from_id, to_id, type, data}
    """
    params = {"from_id": from_id, "to_id": to_id, "type": type, "data": props}

    res = execute_cozo(script, params)
    if res.get("ok"):
        return f"Added fact: {from_name} --[{type}]--> {to_name}"
    return f"Failed: {res.get('message')}"


@mcp.tool()
def add_rule(rule_name: str, datalog_body: str) -> str:
    """
    Define a persistent Datalog rule.
    Args:
        rule_name: Unique name for the rule (e.g., 'father_rule').
        datalog_body: The Cozo Datalog rule (e.g., 'father(F, C) :- fact(F, C, "parent_child", _), person(F, _, data), data->gender == "M"').
    """
    script = """
    ?[name, body] <- [[$name, $body]]
    :put rule {name, body}
    """
    params = {"name": rule_name, "body": datalog_body}

    result = execute_cozo(script, params)
    if result.get("ok"):
        return f"Rule '{rule_name}' saved successfully."
    return f"Failed to save rule: {result.get('message')}"


@mcp.tool()
def run_custom_query(query: str) -> str:
    """
    Run a Datalog query with all stored rules included.
    Args:
        query: The Datalog query to execute (e.g., '?[n] := father(f, c), person(f, n, _)').
    """
    # 1. Fetch stored rules
    rules_block = get_stored_rules()

    # 2. Combine rules and query
    full_script = f"{rules_block}\n{query}"

    # 3. Execute
    result = execute_cozo(full_script)
    if result.get("ok"):
        return json.dumps(result, indent=2)
    return f"Error executing query: {result.get('message')}"


@mcp.tool()
def search_facts(query_string: str) -> str:
    """
    Search for facts based on arbitrary criteria using a Datalog query.
    Convenience wrapper around run_custom_query.
    Args:
        query_string: A Datalog query string.
    """
    return run_custom_query(query_string)


@mcp.tool()
def list_relation_types() -> str:
    """
    List all distinct relationship types currently in use.
    Use this to ensure you reuse existing types (e.g., 'parent_child') instead of creating duplicates (e.g., 'is_parent').
    """
    script = "?[type] := *fact{type}, :distinct type"
    result = execute_cozo(script)
    if result.get("ok"):
        types = [row[0] for row in result.get("rows", [])]
        return f"Existing Relation Types: {', '.join(types)}"
    return "No relations found or error executing query."


@mcp.tool()
def inspect_person_schema() -> str:
    """
    Return a sample of JSON keys/data from existing people to help understand the current schema conventions.
    Use this before adding a new person to ensure you use consistent property names (e.g., 'job' vs 'occupation').
    """
    # Sample 5 people to see their data structure
    script = "?[name, data] := *person{name, data} limit 5"
    result = execute_cozo(script)
    if result.get("ok"):
        rows = result.get("rows", [])
        if not rows:
            return "No people found in database."

        output = ["Sample Data Patterns:"]
        for row in rows:
            name, data = row[0], row[1]
            output.append(f"- {name}: {json.dumps(data)}")
        return "\n".join(output)
    return "Error querying people."


if __name__ == "__main__":
    initialize_schema()
    mcp.run()
