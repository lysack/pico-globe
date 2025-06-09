### Step 1: Find the Position Report

First, the script queries the database for the most recent standard WSPR transmission from the balloon's primary callsign (e.g., `VE7NFR`). This report gives us two critical pieces of information:

1. The balloon's last known location (`locator`).
2. The exact time (`timestamp`) of that position report.

The script constructs a standard SQL query using a simple string for the time comparison (e.g., `WHERE time > '2025-06-08 20:00:00'`), which is a robust and universally accepted format.

### Step 2: Find and Decode the Telemetry Report

This is the key part of the script, based on a crucial user discovery about this specific balloon:

- **The balloon `VE7NFR` is assigned to Channel 536.**
- Its telemetry data is **not** encoded using its own callsign.
- Instead, it transmits a special telemetry "callsign" that follows a pattern derived from its channel number.

The script uses this logic:

1. It calculates the correct telemetry pattern. For Channel 536, the pattern is **`Q_6%`**.
   - `Q` is a general identifier for this type of telemetry.
   - `_` is a literal underscore (escaped as `\\_` in the Python f-string).
   - `6` is the last digit of the channel number (53**6**).
   - `%` is a wildcard to match the rest of the encoded data.
2. It performs a second query, searching for a transmission with a callsign `LIKE 'Q_6%'` that occurred in the 60 minutes immediately following the position report from Step 1.
3. If it finds a matching telemetry packet (e.g., `Q_6FCUJ2`), it passes this string to a decoder function which converts the hexadecimal characters into human-readable data like altitude, voltage, temperature, etc.
