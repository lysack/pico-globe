import urllib.request
import json
import time
from datetime import datetime, timezone, timedelta
import urllib.parse

# --- Configuration ---
TARGET_CALLSIGN = "VE7NFR" 

# *** From user discovery: The telemetry pattern is derived from the assigned channel. ***
CHANNEL_NUMBER = 536 

# How many hours back to search for the initial position spot.
SEARCH_HOURS = 24

# The correct API endpoint for direct database queries.
WSPR_DB_URL = "http://db1.wspr.live/"

# --- Main Logic ---

def execute_query(sql_query):
    """Executes a raw SQL query against the WSPR Live database using urllib."""
    try:
        url = f"{WSPR_DB_URL}?query={urllib.parse.quote_plus(sql_query)}"
        print(f"\nDEBUG: Full URL being requested:\n{url}")
        contents = urllib.request.urlopen(url).read()
        return contents.decode("UTF-8").strip().split("\n")
    except Exception as e:
        print(f"Error querying WSPR database: {e}")
        return None

def parse_db_time(time_str):
    """Parses the 'YYYY-MM-DD HH:MM:SS' time string from the database into a Unix timestamp."""
    try:
        dt_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        return int(dt_obj.replace(tzinfo=timezone.utc).timestamp())
    except (ValueError, TypeError):
        return 0 # Return a default value on parsing error

def get_latest_spot(callsign, hours_ago=24):
    """Gets the latest position spot using a direct and robust SQL query."""
    print(f"Searching for latest position spot for {callsign}...")
    
    # Convert timestamp to a 'YYYY-MM-DD HH:MM:SS' string for the SQL query
    start_ts = int(time.time()) - (hours_ago * 3600)
    start_time_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    # This query uses a simple string comparison for the time, which is more robust.
    sql = (
        f"SELECT toString(time) as stime, band, tx_sign, tx_loc, tx_lat, tx_lon, power, stime "
        f"FROM wspr.rx "
        f"WHERE (time > '{start_time_str}') AND (tx_sign = '{callsign}') "
        f"ORDER BY time DESC LIMIT 1"
    )
    
    results = execute_query(sql)
    
    if not results or not results[0]:
        print(f"No position spots found for {callsign} in the last {hours_ago} hours.")
        return None
        
    # Parse the tab-separated response
    spot_data = results[0].split("\t")
    spot = {
        'time': parse_db_time(spot_data[0]),
        'band': spot_data[1],
        'callsign': spot_data[2],
        'locator': spot_data[3],
        'latitude': float(spot_data[4]),
        'longitude': float(spot_data[5]),
        'power': float(spot_data[6]),
        'stime': spot_data[7]
    }
    return spot

def find_telemetry_spot(position_spot, balloon_id_pattern):
    """Find the first telemetry spot in the last SEARCH_HOURS hours."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=SEARCH_HOURS)
    print(f"Searching for telemetry pattern '{balloon_id_pattern}' from {start_time.strftime('%H:%M:%S')} to {end_time.strftime('%H:%M:%S')}...")
    query = f"""
        SELECT toString(time) as stime, band, tx_sign, tx_loc, tx_lat, tx_lon, power, stime 
        FROM wspr.rx 
        WHERE (time BETWEEN '{start_time.strftime("%Y-%m-%d %H:%M:%S")}' AND '{end_time.strftime("%Y-%m-%d %H:%M:%S")}' )
        AND (tx_sign LIKE '{balloon_id_pattern}')
        ORDER BY time DESC
        LIMIT 1
    """
    try:
        response = execute_query(query)
        if response and len(response) > 0:
            # Parse the tab-separated response into a dictionary
            fields = ["stime", "band", "tx_sign", "tx_loc", "tx_lat", "tx_lon", "power", "stime2"]
            values = response[0].split("\t")
            telemetry_dict = dict(zip(fields, values))
            return telemetry_dict
    except Exception as e:
        print(f"Error querying WSPR database: {e}")
    print(f"No potential telemetry spots found with pattern '{balloon_id_pattern}'.")
    return None

def decode_traquito_telemetry(telemetry_string):
    """Decodes a Traquito telemetry string into a dictionary of values."""
    print(f"Decoding telemetry string: '{telemetry_string}'")
    # Traquito telemetry format: QJ6RDC (example)
    # Remove underscore check, accept any string starting with 'Q' and length >= 6
    if not telemetry_string.startswith('Q') or len(telemetry_string) < 6:
        print("Invalid or unrecognized telemetry format: Must start with 'Q' and be at least 6 chars.")
        return None

    # The rest of the decoding logic remains the same as before
    # Example: QJ6RDC
    # Q: fixed
    # J: md (altitude)
    # 6: temp
    # R: voltage
    # D: speed
    # C: GPS sats/uptime
    def char_to_val(c):
        return ord(c) - ord('A')

    md = char_to_val(telemetry_string[1])
    temp = char_to_val(telemetry_string[2])
    volt = char_to_val(telemetry_string[3])
    speed = char_to_val(telemetry_string[4])
    gps = char_to_val(telemetry_string[5])

    # Example decoding math (adjust as needed for your protocol):
    altitude = md * 20  # meters
    temperature_c = temp - 10  # Celsius
    voltage = 3.0 + volt * 0.1  # Volts
    speed_kmh = speed * 2  # km/h
    gps_sats = gps & 0x7  # lower 3 bits
    uptime_hours = gps >> 3  # upper bits

    return {
        'altitude': altitude,
        'temperature_c': temperature_c,
        'voltage': voltage,
        'speed_kmh': speed_kmh,
        'gps_sats': gps_sats,
        'uptime_hours': uptime_hours,
        'md': md
    }


if __name__ == "__main__":
    print("--- Traquito Telemetry Decoder ---")
    
    position_spot = get_latest_spot(TARGET_CALLSIGN, hours_ago=SEARCH_HOURS)
    
    if position_spot:
        print("\nFound Position Spot:")
        pos_time = datetime.fromtimestamp(position_spot['time'], tz=timezone.utc)
        print(f"  - Callsign:    {position_spot['callsign']}")
        print(f"  - Time:        {pos_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  - Band:        {position_spot['band']}")
        print(f"  - Location:    {position_spot['locator']}")
        print(f"  - Latitude:    {position_spot['latitude']}")
        print(f"  - Longitude:   {position_spot['longitude']}")
        print(f"  - Power:       {position_spot['power']} dBm")
        
        # Using the channel-based telemetry pattern discovered by the user.
        id1 = 'Q'
        id3 = str(CHANNEL_NUMBER)[-1]
        # Use an unescaped underscore for the SQL LIKE clause.
        balloon_id_pattern = f"{id1}_{id3}%"
        
        telemetry_spot = find_telemetry_spot(position_spot, balloon_id_pattern)
        
        if telemetry_spot:
            telemetry_data = decode_traquito_telemetry(telemetry_spot['tx_sign'])
            
            if telemetry_data:
                print("\n--- DECODED TELEMETRY ---")
                print(f"  - {'Altitude':<18}: {telemetry_data['altitude']} m")
                print(f"  - {'Temperature':<18}: {telemetry_data['temperature_c']} °C")
                print(f"  - {'Voltage':<18}: {telemetry_data['voltage']:.2f} V")
                print(f"  - {'Speed':<18}: {telemetry_data['speed_kmh']} km/h")
                print(f"  - {'GPS Satellites':<18}: {telemetry_data['gps_sats']}")
                print(f"  - {'Uptime':<18}: {telemetry_data['uptime_hours']} hours")
                print("-------------------------")

    print("\nScript finished.")
