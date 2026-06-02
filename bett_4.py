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

# --- COLOR CONSTANTS ---
COLRED = "\033[31m"
COLGRN = "\033[32m"
COLYEL = "\033[33m"
COLBLU = "\033[34m"
COLMAG = "\033[35m"
COLCYN = "\033[36m"
COLWHT = "\033[37m"
COLRST = "\033[0m"
COLBGR = "\033[1;32m"
COLBYL = "\033[1;33m"
COLBBL = "\033[1;34m"
COLBMG = "\033[1;35m"
COLBCY = "\033[1;36m"

CAR_ASCII="""

             █████████                           █▀▀▀▀▀▀▀▀▀▀█ 
             ██████████                         ██          ██  
        ██████████████████████                 ███▄▄▄▄▄▄▄▄▄▄███
        ███▒▒▒██████████▒▒▒████                ████████████████
        ██▒▒▒▒▒████████▒▒▒▒▒███                ▀▒▒▒▀▀▀▀▀▀▀▀▒▒▒▀
           ▒▒▒          ▒▒▒                     ▒▒▒        ▒▒▒

"""


# --- DOUBLE BUFFER CANVAS ENGINE ---
class TerminalCanvas:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.clear()

    def clear(self):
        # Two parallel grids: one for chars, one for their color strings
        self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.colors = [[COLRST for _ in range(self.width)] for _ in range(self.height)]

    def draw_string(self, x, y, text, color=COLRST):
        """Draws a plain string onto the canvas at a specific location."""
        for i, char in enumerate(text):
            tx = x + i
            if 0 <= tx < self.width and 0 <= y < self.height:
                self.grid[y][tx] = char
                self.colors[y][tx] = color

    def blit(self, source_text, start_x, start_y, color=COLRST):
        """Blits multi-line newline-separated ASCII blocks onto the canvas."""
        lines = source_text.strip("\n").split("\n")
        for row_idx, line in enumerate(lines):
            for col_idx, char in enumerate(line):
                tx = start_x + col_idx
                ty = start_y + row_idx
                if 0 <= tx < self.width and 0 <= ty < self.height:
                    self.grid[ty][tx] = char
                    self.colors[ty][tx] = color

    def render(self):
        """Compiles the canvas down to a compressed string with color maps."""
        output = ["\033[H"] # Return cursor to top-left
        for y in range(self.height):
            current_color = COLRST
            line_segments = []
            for x in range(self.width):
                char_color = self.colors[y][x]
                if char_color != current_color:
                    line_segments.append(char_color)
                    current_color = char_color
                line_segments.append(self.grid[y][x])
            if current_color != COLRST:
                line_segments.append(COLRST)
            output.append("".join(line_segments) + "\n")
        return "".join(output)

# --- MATH & PARSING UTILITIES ---
def rad2deg(rad):
    return rad * (180.0 / math.pi)

def yaw2direction(yawdeg):
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((yawdeg + 22.5) % 360 / 45)
    return directions[idx]

def parse_packet(data):
    if len(data) < 324: return None
    return dict(zip(FORZA_FIELDS, struct.unpack(FORZA_FORMAT, data[:324])))

def make_bar_chars(value_0_255):
    """Creates raw characters for a 20-character meter bar."""
    pct = value_0_255 / 255.0
    filled_chars = int(pct * 20)
    return "█" * filled_chars + "░" * (20 - filled_chars)



def draw_terminal():
    pass


# --- INITIALIZATION ---
UDP_IP = "0.0.0.0"
UDP_PORT = 9999
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

graph_width = 76
speed_history = collections.deque([0.0] * graph_width, maxlen=graph_width)
max_observed_speed = 100.0

# Initialize canvas size (Width x Height)
canvas = TerminalCanvas(120, 40)
os.system('clear')
print("\033[?25l") # Hide cursor

try:
    while True:
        raw_data, addr = sock.recvfrom(1024)
        tele = parse_packet(raw_data)
        if not tele: continue
        
        canvas.clear()
        
        # Calculations
        speed_mph = tele["Speed"] * 2.23694
        speed_history.append(speed_mph)
        if speed_mph > max_observed_speed:
            max_observed_speed = speed_mph
            
        gear_map = {0: "R", 11: "N"}
        gear_display = gear_map.get(tele["Gear"], str(tele["Gear"]))
        
        dPitch = rad2deg(tele["Pitch"])
        dRoll = rad2deg(tele["Roll"])
        dYaw = rad2deg(tele["Yaw"])
        direction_str = yaw2direction(dYaw)
        
        # --- BLIT COMPONENT WIDGETS ---
        
        # Title Block
        canvas.draw_string(0, 0, "=== Beomamgi's Experimental Telemetry Tool ===", COLBCY)
        status_str = '[ RACING ]' if tele['IsRaceOn'] else '[ MENUS ]'
        canvas.draw_string(0, 1, f"Status: {status_str}", COLWHT)
        
        # Telemetry Text Data
        canvas.draw_string(0, 3, f"SPEED:  {speed_mph:5.1f} MPH", COLBGR)
        canvas.draw_string(0, 4, f"GEAR:   [{gear_display}]", COLBYL)
        canvas.draw_string(0, 5, f"RPM:    {tele['CurrentEngineRpm']:5.0f} / {tele['EngineMaxRpm']:.0f}", COLBCY)
        
        # Controls Bars
        canvas.draw_string(0, 7, "THROTTLE: ", COLWHT)
        canvas.draw_string(10, 7, make_bar_chars(tele['Accel']), COLGRN)
        canvas.draw_string(0, 8, "BRAKE:    ", COLWHT)
        canvas.draw_string(10, 8, make_bar_chars(tele['Brake']), COLRED)
        
        # Car Silhouette Blit (Placed right next to stats at x=40, y=3)
        canvas.blit(CAR_ASCII, 42, 2, COLWHT)
        
        # Orientation Info Block
        canvas.draw_string(0, 10, " [ CAR ORIENTATION ]", COLWHT)
        canvas.draw_string(2, 11, f"Yaw:   {dYaw:6.2f}° ({direction_str})", COLBYL)
        canvas.draw_string(2, 12, f"Pitch: {dPitch:6.2f}°", COLBYL)
        canvas.draw_string(2, 13, f"Roll:  {dRoll:6.2f}°", COLBYL)
        canvas.draw_string(2, 14, f"Lap:   {tele['LapNumber']}", COLWHT)
        canvas.draw_string(2, 15, f"Pos:   {tele['RacePosition']}", COLWHT)
        
        # Orientation Vector Mini-Widget
        dx = math.sin(tele["Yaw"])
        dy = math.cos(tele["Yaw"])
        target_x = 28 + round(dx * 2)
        target_y = 13 - round(dy * 2)
        canvas.draw_string(28, 13, "o", COLWHT)
        if (target_x, target_y) != (28, 13):
            canvas.draw_string(target_x, target_y, "▲", COLRED)
            
        # Draw Rolling History Graph
        canvas.draw_string(0, 18, f" [ SPEED HISTORY - MAX OBSERVED: {max_observed_speed:.1f} MPH ]", COLWHT)
        
        graph_height = 10
        for row in range(graph_height, 0, -1):
            # Define the exact window this specific row represents
            row_top = (row / graph_height) * max_observed_speed
            row_bottom = ((row - 1) / graph_height) * max_observed_speed
            row_half = row_bottom + (row_top - row_bottom) * 0.5
            
            for col_idx, val in enumerate(speed_history):
                graph_x = 2 + col_idx
                graph_y = 28 - row # Fits perfectly on a 28-row canvas
                
                if val > row_top:
                    # The value goes past this row -> it's part of the body fill
                    canvas.draw_string(graph_x, graph_y, "▒", COLBCY)
                elif val >= row_bottom:
                    # The value terminates INSIDE this row -> it's the peak/top edge!
                    if val >= row_half:
                        canvas.draw_string(graph_x, graph_y, "█", COLBCY) # Solid full-cap
                    else:
                        canvas.draw_string(graph_x, graph_y, "▄", COLBCY) # Solid half-cap

                    
        # Render the current frame to terminal screen
        print(canvas.render(), end="")

except KeyboardInterrupt:
    print("\033[?25h") # Restore cursor
    print("\nDashboard closed.")
    sock.close()
