import json
import uuid
from collections import defaultdict

def get_geoip_data(ip_address):
    """
    Placeholder for GeoIP lookup.
    In a real-world scenario, you would use a library like GeoIP2 to resolve
    the IP address to a geographical location.
    
    Example using geoip2:
    # from geoip2 import database
    # reader = database.Reader('/path/to/GeoLite2-City.mmdb')
    # try:
    #     response = reader.city(ip_address)
    #     return {
    #         "lat": response.location.latitude,
    #         "lon": response.location.longitude,
    #         "country": response.country.iso_code
    #     }
    # except Exception:
    #     return {"lat": None, "lon": None, "country": "N/A"}
    """
    # For this script, we'll return placeholder values.
    return {"lat": None, "lon": None, "country": "N/A"}

def analyze_session(session_logs):
    """
    Analyzes a list of log entries for a single session to determine the
    event label and severity based on the attacker's actions.
    """
    # Default values for a simple connection with no further action
    label = "scan"
    severity = 1
    
    commands = []
    has_successful_login = False
    has_failed_login = False

    for log in session_logs:
        event_id = log.get("eventid")
        if event_id == "cowrie.login.success":
            has_successful_login = True
        elif event_id == "cowrie.login.failed":
            has_failed_login = True
        elif event_id == "cowrie.command.input":
            commands.append(log.get("input", "").lower())

    if has_successful_login:
        # If the attacker logged in, severity increases. Label defaults to reconnaissance.
        label = "reconnaissance"
        severity = 2
        # Check for more specific malicious commands
        for cmd in commands:
            if "miner" in cmd:
                return "cryptominer-check", 4 # High severity for cryptojacking attempts
            if "/ip cloud print" in cmd:
                return "mikrotik-recon", 3 # Specific recon for MikroTik routers
            if "telegramdesktop" in cmd or "smsd" in cmd:
                return "info-gathering", 3 # Attempt to steal user data
    elif has_failed_login:
        # If there are failed logins but no success, it's likely a brute-force attack.
        label = "brute-force"
        severity = 2

    return label, severity

def parse_cowrie_logs(input_file="cowrie.json", output_file="events.json"):
    """
    Reads a file with line-delimited JSON Cowrie logs, processes them,
    and writes a new JSON file in the specified format.
    """
    sessions = defaultdict(list)

    # Step 1: Read the input file and group logs by session ID
    try:
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    session_id = log.get("session")
                    if session_id:
                        sessions[session_id].append(log)
                except json.JSONDecodeError:
                    print(f"Warning: Skipping invalid JSON line: {line.strip()}")
                    continue
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return

    output_events = []
    
    # Step 2: Process each session to create one summary event
    for session_id, logs in sessions.items():
        if not logs:
            continue
        
        # Sort logs chronologically
        logs.sort(key=lambda x: x.get("timestamp", ""))
        
        # The first log should be the connection event
        first_log = logs[0]
        if first_log.get("eventid") != "cowrie.session.connect":
            continue # Skip sessions that don't start with a connection

        # Step 3: Analyze the entire session's activity
        label, severity = analyze_session(logs)
        
        src_ip = first_log.get("src_ip")
        
        # Get location data (using our placeholder function)
        geoip_data = get_geoip_data(src_ip)

        # Step 4: Construct the new event object
        event = {
            "id": str(uuid.uuid4()),
            "ts": first_log.get("timestamp"),
            "src_ip": src_ip,
            "lat": geoip_data["lat"],
            "lon": geoip_data["lon"],
            "country": geoip_data["country"],
            "port": first_log.get("dst_port"),
            "proto": "tcp" if first_log.get("protocol") == "ssh" else first_log.get("protocol"),
            "label": label,
            "severity": severity
        }
        output_events.append(event)
        
    # Step 5: Write the list of new events to the output file
    with open(output_file, 'w') as f:
        json.dump(output_events, f, indent=2)
        
    print(f"✅ Success! Processed {len(sessions)} sessions and created '{output_file}'.")

if __name__ == "__main__":
    parse_cowrie_logs()