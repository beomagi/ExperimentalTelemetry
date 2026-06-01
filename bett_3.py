#!/usr/bin/env python3
import socket
import struct
import math
import os
import collections

# --- FORZA PACKET CONFIGURATION ---
FORZA_FORMAT = '<iI12f3f4f4f4f4i4i4f4f4f4f5iI2f3f3f4f3f4fH5BB3bx'
FORZA_FIELDS = [
    "IsRaceOn", "TimestampMS", "EngineMaxRpm", "EngineIdleRpm", "CurrentEngineRpm",
    "AccelerationX", "AccelerationY", "AccelerationZ", "VelocityX", "VelocityY", "VelocityZ",
    "AngularVelocityX", "AngularVelocityY", "AngularVelocityZ", "Yaw", "Pitch", "Roll",
    "SuspensionTravelFL", "SuspensionTravelFR", "SuspensionTravelRL", "SuspensionTravelRR",
    "TireSlipRatioFL", "TireSlipRatioFR", "TireSlipRatioRL", "TireSlipRatioRR",
    "WheelRotationSpeedFL", "WheelRotationSpeedFR", "WheelRotationSpeedRL", "WheelRotationSpeedRR",
    "WheelOnRumbleStripFL", "WheelOnRumbleStripFR", "WheelOnRumbleStripRL", "WheelOnRumbleStripRR",
    "WheelInPuddleFL", "WheelInPuddleFR", "WheelInPuddleRL", "WheelInPuddleRR",
    "SurfaceRumbleFL", "SurfaceRumbleFR", "SurfaceRumbleRL", "SurfaceRumbleRR",
    "TireSlipAngleFL", "TireSlipAngleFR", "TireSlipAngleRL", "TireSlipAngleRR",
    "TireCombinedSlipFL", "TireCombinedSlipFR", "TireCombinedSlipRL", "TireCombinedSlipRR",
    "SuspensionTravelMetersFL", "SuspensionTravelMetersFR", "SuspensionTravelMetersRL", "SuspensionTravelMetersRR",
    "CarOrdinal", "CarClass", "CarPerformanceIndex", "DrivetrainType", "NumCylinders",
    "CarGroup", "SmashableVelDiff", "SmashableMass", "PositionX", "PositionY", "PositionZ",
    "Speed", "Power", "Torque", "TireTempFL", "TireTempFR", "TireTempRL", "TireTempRR",
    "Boost", "Fuel", "DistanceTraveled", "BestLap", "LastLap", "CurrentLap", "CurrentRaceTime",
    "LapNumber", "RacePosition", "Accel", "Brake", "Clutch", "HandBrake", "Gear", "Steer",
    "NormalizedDrivingLine", "NormalizedAIBrakeDifference"
]

COLRED = "\033[31m"
COLGRN = "\033[32m"
COLYEL = "\033[33m"
COLBLU = "\033[34m"
COLMAG = "\033[35m"
COLCYN = "\033[36m"
COLWHT = "\033[37m"
COLRST = "\033[0m"
COLBRD = "\033[1;31m"
COLBGR = "\033[1;32m"
COLBYL = "\033[1;33m"
COLBBL = "\033[1;34m"
COLBMG = "\033[1;35m"
COLBCY = "\033[1;36m"



car="""
             █████████  
             ██████████  
        ██████████████████████       
        ███▒▒▒██████████▒▒▒████
        ██▒▒▒▒▒████████▒▒▒▒▒███
           ▒▒▒          ▒▒▒

"""


def rad2deg(rad):
    return rad * (180.0 / math.pi)

def yaw2direction(yawdeg):
    # Convert Yaw in degrees to a compass direction (N, NE, E, SE, S, SW, W, NW)
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((yawdeg + 22.5) % 360 / 45)
    return directions[idx]

def parse_packet(data):
    if len(data) < 324: return None
    return dict(zip(FORZA_FIELDS, struct.unpack(FORZA_FORMAT, data[:324])))

# --- UI DRAWING HELPERS ---
def make_bar(value_0_255, color_code):
    """Creates a 20-character filled visual bar for peddle inputs."""
    pct = value_0_255 / 255.0
    filled_chars = int(pct * 20)
    bar = "█" * filled_chars + "░" * (20 - filled_chars)
    return f"\033[{color_code}m{bar}\033[0m"

def draw_orientation(yaw_rad):
    """Draws a 5x5 text matrix showing car direction based on Yaw."""
    # Forza Yaw: 0 = North/Forward, positive is clockwise/counter-clockwise depending on game version
    # Standard math mapping:
    dx = math.sin(yaw_rad)
    dy = math.cos(yaw_rad)
    
    # Grid initialization
    grid = [[" " for _ in range(5)] for _ in range(5)]
    grid[2][2] = "o" # Center pivot (car location)
    
    # Calculate vector tip offset from center
    target_x = 2 + round(dx * 2)
    target_y = 2 - round(dy * 2) # Invert Y for terminal coordinates
    
    # Bound limits to keep grid safe
    target_x = max(0, min(4, target_x))
    target_y = max(0, min(4, target_y))
    
    if (target_x, target_y) != (2, 2):
        grid[target_y][target_x] = "▲"
        
    return grid

def draw_ascii_graph(history, max_val, height=6):
    """Generates an ASCII bar chart from a rolling history buffer."""
    if not max_val: max_val = 1
    graph_lines = []
    
    for row in range(height, 0, -1):
        line_chars = []
        threshold = (row / height) * max_val
        for val in history:
            if val >= threshold:
                line_chars.append("█")
            elif val >= (threshold - (1/height * max_val) * 0.5):
                line_chars.append("▄")
            else:
                line_chars.append(" ")
        graph_lines.append("".join(line_chars))
    return graph_lines

# --- INITIALIZATION & MAIN LOOP ---
UDP_IP = "0.0.0.0"
UDP_PORT = 9999

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

# Track historical speeds for the telemetry graph (stores last 60 ticks)
graph_width = 60
speed_history = collections.deque([0.0] * graph_width, maxlen=graph_width)
max_observed_speed = 100.0

# Clear the console entirely once at startup
os.system('clear')

print("\033[?25l") # Hide terminal cursor for cleaner rendering
print("Waiting for Forza telemetry stream...")

try:
    while True:
        raw_data, addr = sock.recvfrom(1024)
        tele = parse_packet(raw_data)
        if not tele: continue
        
        # Calculations
        speed_mph = tele["Speed"] * 2.23694
        speed_history.append(speed_mph)
        if speed_mph > max_observed_speed:
            max_observed_speed = speed_mph
            
        gear_map = {0: "R", 11: "N"}
        gear_display = gear_map.get(tele["Gear"], str(tele["Gear"]))
        
        # Build UI layout
        ui_buffer = []
        
        # Move cursor to top-left (0,0) without clearing, preventing structural screen flicker
        ui_buffer.append("\033[H") 
        ui_buffer.append("=== Beomamgi's Experimental Telemetry Tool ===\n")
        ui_buffer.append(f"Status: {'[ RACING ]' if tele['IsRaceOn'] else '[ MENUS  ]'}\n\n")
        
        # Main stats block
        ui_buffer.append(f"  SPEED: {COLBGR}{speed_mph:5.1f} MPH{COLRST}   |   GEAR: [{COLYEL}{gear_display}{COLRST}]   |   RPM: {COLBCY}{tele['CurrentEngineRpm']:5.0f}{COLRST} / {COLBMG}{tele['EngineMaxRpm']:.0f}{COLRST}\n")
        
        # Throttle & Brake visual status meters
        ui_buffer.append(f"  THROTTLE: {make_bar(tele['Accel'], '32')}   |   BRAKE: {make_bar(tele['Brake'], '31')}\n\n")
        
        # Generate Orientation Grid side-by-side with basic details
        ui_buffer.append("  [ CAR ORIENTATION ]\n")
        orient_grid = draw_orientation(tele["Yaw"])
        tele["dPitch"] = rad2deg(tele["Pitch"])
        tele["dRoll"] = rad2deg(tele["Roll"])
        tele["dYaw"] = rad2deg(tele["Yaw"])
        tele["Direction"] = yaw2direction(tele["dYaw"])
        labels = [
            f"  Yaw:   {COLYEL}{tele['dYaw']:6.2f}{COLRST}° ({COLBBL}{tele['Direction']}{COLRST})",
            f"  Pitch: {COLYEL}{tele['dPitch']:6.2f}{COLRST}°",
            f"  Roll:  {COLYEL}{tele['dRoll']:6.2f}{COLRST}°",
            f"  Lap:   {tele['LapNumber']}",
            f"  Pos:   {tele['RacePosition']}"
        ]
        for i in range(5):
            grid_row = " ".join(orient_grid[i])
            ui_buffer.append(f"    {grid_row}       {labels[i]}\n")
            
        # Draw Rolling Velocity Strip Chart
        ui_buffer.append(f"\n  [ SPEED HISTORY GRAPH - MAX OBSERVED: {max_observed_speed:.1f} MPH ]\n")
        graph_rows = draw_ascii_graph(speed_history, max_observed_speed)
        for row_str in graph_rows:
            ui_buffer.append(f"  {row_str}\n")
            
        # Write entire updated frame onto screen at once
        print("".join(ui_buffer), end="")

except KeyboardInterrupt:
    print("\033[?25h") # Restore original terminal cursor state
    print("\nDashboard closed.")
    sock.close()
