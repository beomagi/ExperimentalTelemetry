#!/usr/bin/env python3
import socket
import struct
import math
import os
import collections
import re

CANVAS_WIDTH = 150
CANVAS_HEIGHT = 40
glbcntr=0 #used for graph "texture"

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

#Tire Slip Ratio thresholds for color coding (0-100% scale)
SLIPRATIOTHRESHOLD_LOW = 50   # slipping forward, backwards, accelerating, or decelerating
SLIPRATIOTHRESHOLD_HIGH = 100
SLIPANGLETHRESHOLD_LOW = 50   # slipping slideways, drifting, understeering, or oversteering
SLIPANGLETHRESHOLD_HIGH = 100
SLIPCOMBITHRESHOLD_LOW = 50   # overall slippage
SLIPCOMBITHRESHOLD_HIGH = 100


# --- COLOR CONSTANTS ---
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
# Pattern match terminal color codes for stripping
ANSI_ESCAPE_RE = re.compile(r'\033\[[0-9;]*[a-zA-Z]')


CAR_ASCII=f"""

             ▄███████▄                           ▄██████████▄
             █#W#████████#R#█                         █#W#████████████#R#█  
        ▄██████████████████▄▄                  ████████████████
        ███#Tb#▒▒▒#R#██████████#Tf#▒▒▒#R#███▄                ████████████████
        ▀█#Tb#▒▒▒▒▒#R#████████#Tf#▒▒▒▒▒#R#███                ▀#Tl#▒▒▒#R#▀▀▀▀▀▀▀▀#Tr#▒▒▒#R#▀
           #Tb#▒▒▒#R#          #Tf#▒▒▒#R#                     #Tl#▒▒▒#R#        #Tr#▒▒▒#R#

"""


# --- DOUBLE BUFFER CANVAS ENGINE ---
class TerminalCanvas:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.clear()

    def clear(self):
        self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.colors = [[COLRST for _ in range(self.width)] for _ in range(self.height)]

    def draw_string(self, x, y, text, color=COLRST):
        """Draws a string onto the canvas, automatically parsing embedded ANSI codes 
        to switch colors without taking up physical layout space."""
        current_color = color
        current_x = x
        
        # Split the string by ANSI sequences, keeping the delimiters
        tokens = ANSI_ESCAPE_RE.split(text)
        codes = ANSI_ESCAPE_RE.findall(text)
        
        # Interleave text segments and ANSI changes
        for idx, token in enumerate(tokens):
            # Process the visible text segment
            for char in token:
                if 0 <= current_x < self.width and 0 <= y < self.height:
                    self.grid[y][current_x] = char
                    self.colors[y][current_x] = current_color
                current_x += 1 # Only advance the layout index for visible characters
                
            # If there's an ANSI code immediately following this text segment, update the active color
            if idx < len(codes):
                current_color = codes[idx]

    def blit(self, source_text, start_x, start_y, default_color=COLRST):
        """Blits multi-line newline-separated ASCII blocks onto the canvas,
        safely handling embedded ANSI color codes without breaking layout alignment."""
        lines = source_text.strip("\n").split("\n")
        
        for row_idx, line in enumerate(lines):
            current_x = start_x
            ty = start_y + row_idx
            current_color = default_color
            
            # Split the line by ANSI sequences, keeping the delimiters
            tokens = ANSI_ESCAPE_RE.split(line)
            codes = ANSI_ESCAPE_RE.findall(line)
            
            for idx, token in enumerate(tokens):
                # Process literal visible characters
                for char in token:
                    if 0 <= current_x < self.width and 0 <= ty < self.height:
                        self.grid[ty][current_x] = char
                        self.colors[ty][current_x] = current_color
                    current_x += 1 # Only advance horizontal position for actual visible characters
                    
                # If an ANSI escape code follows this text token, update the drawing color
                if idx < len(codes):
                    current_color = codes[idx]


    def render(self):
        """Compiles the canvas down to a compressed string with color maps."""
        output = ["\033[H"]
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

# --- DRAWING ITEMS ---

def draw_boundary_box(canvas, x, y, width, height, color=COLRST):
    horizontal = "─"
    vertical = "│"
    tl_corner = "┌"
    tr_corner = "┐"
    bl_corner = "└"
    br_corner = "┘"
    
    # Draw corners
    canvas.draw_string(x, y, tl_corner, color)
    canvas.draw_string(x + width - 1, y, tr_corner, color)
    canvas.draw_string(x, y + height - 1, bl_corner, color)
    canvas.draw_string(x + width - 1, y + height - 1, br_corner, color)
    
    # Draw horizontal edges
    for i in range(1, width - 1):
        canvas.draw_string(x + i, y, horizontal, color)
        canvas.draw_string(x + i, y + height - 1, horizontal, color)
    
    # Draw vertical edges
    for j in range(1, height - 1):
        canvas.draw_string(x, y + j, vertical, color)
        canvas.draw_string(x + width - 1, y + j, vertical, color)

def draw_title_block(canvas, tele, x=0, y=0):
    canvas.draw_string(x, y, "=== Beomamgi's Experimental Telemetry Tool ===", COLBCY)
    status_str = '[ RACING ]' if tele['IsRaceOn'] else '[ MENUS ]'
    canvas.draw_string(x, y + 1, f"Status: {status_str}", COLWHT)

def draw_telemetry_text(canvas, tele, gear_display, x=0, y=3):
    canvas.draw_string(x, y, f"SPEED:  {speed_mph:5.1f} MPH", COLBGR)
    canvas.draw_string(x, y + 1, f"GEAR:   [{gear_display}]", COLBYL)
    canvas.draw_string(x, y + 2, f"RPM:    {tele['CurrentEngineRpm']:5.0f} / {tele['EngineMaxRpm']:.0f}", COLBCY)

def draw_input_bars(canvas, tele, x=0, y=7):
    canvas.draw_string(x, y, "THROTTLE: ", COLWHT)
    canvas.draw_string(x + 10, y, make_bar_chars(tele['Accel']), COLGRN)
    canvas.draw_string(x, y + 1, "BRAKE:    ", COLWHT)
    canvas.draw_string(x + 10, y + 1, make_bar_chars(tele['Brake']), COLRED)

def draw_car_silhouette(canvas, tele, x=42, y=2):
    #combines tires for front/rear, left/right for the diagram
    tireback=max(tele['SlipCombiPcrRL'],tele['SlipCombiPcrRR'])
    tirefrnt=max(tele['SlipCombiPcrFL'],tele['SlipCombiPcrFR'])
    tireleft=max(tele['SlipCombiPcrFL'],tele['SlipCombiPcrRL'])
    tirerigt=max(tele['SlipCombiPcrFR'],tele['SlipCombiPcrRR'])
    TireColTB=colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tireback)
    TireColTF=colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tirefrnt)
    TireColTL=colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tireleft)
    TireColTR=colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tirerigt)

    CAR_ASCIId=CAR_ASCII.replace("#W#", f"{COLBBL}").replace("#R#", f"{COLRST}").replace("#Tb#", TireColTB).replace("#Tf#", TireColTF).replace("#Tl#", TireColTL).replace("#Tr#", TireColTR)
    canvas.blit(CAR_ASCIId, x, y, COLWHT)


def colorbyrange(col1,col2,col3,threshold1, threshold2, value):
    if value < threshold1:
        return col1
    elif value < threshold2:
        return col2
    else:
        return col3

def draw_tire_slip_info(canvas, tele, x=42, y=15):
    canvas.draw_string(x, y, " [ TIRE SLIP RATIO ]", COLWHT)
    canvas.draw_string(x + 5, y + 1, f"{tele['SlipRatioPcrFL']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPRATIOTHRESHOLD_LOW,SLIPRATIOTHRESHOLD_HIGH,tele['SlipRatioPcrFL']))
    canvas.draw_string(x + 5, y + 2, f"{tele['SlipRatioPcrFR']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPRATIOTHRESHOLD_LOW,SLIPRATIOTHRESHOLD_HIGH,tele['SlipRatioPcrFR']))
    canvas.draw_string(x + 18, y + 1, f"{tele['SlipRatioPcrRL']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPRATIOTHRESHOLD_LOW,SLIPRATIOTHRESHOLD_HIGH,tele['SlipRatioPcrRL']))
    canvas.draw_string(x + 18, y + 2, f"{tele['SlipRatioPcrRR']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPRATIOTHRESHOLD_LOW,SLIPRATIOTHRESHOLD_HIGH,tele['SlipRatioPcrRR']))
    canvas.draw_string(x, y+3, " [ TIRE SLIP SIDEWAYS RATIO ]", COLWHT)
    canvas.draw_string(x + 5, y + 4, f"{tele['SlipAnglePcrFL']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPANGLETHRESHOLD_LOW,SLIPANGLETHRESHOLD_HIGH,tele['SlipAnglePcrFL']))
    canvas.draw_string(x + 5, y + 5, f"{tele['SlipAnglePcrFR']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPANGLETHRESHOLD_LOW,SLIPANGLETHRESHOLD_HIGH,tele['SlipAnglePcrFR']))
    canvas.draw_string(x + 18, y + 4, f"{tele['SlipAnglePcrRL']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPANGLETHRESHOLD_LOW,SLIPANGLETHRESHOLD_HIGH,tele['SlipAnglePcrRL']))
    canvas.draw_string(x + 18, y + 5, f"{tele['SlipAnglePcrRR']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPANGLETHRESHOLD_LOW,SLIPANGLETHRESHOLD_HIGH,tele['SlipAnglePcrRR']))
    canvas.draw_string(x, y+6, " [ TIRE COMBINED SLIP RATIO ]", COLWHT)
    canvas.draw_string(x + 5, y + 7, f"{tele['SlipCombiPcrFL']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tele['SlipCombiPcrFL']))
    canvas.draw_string(x + 5, y + 8, f"{tele['SlipCombiPcrFR']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tele['SlipCombiPcrFR']))
    canvas.draw_string(x + 18, y + 7, f"{tele['SlipCombiPcrRL']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tele['SlipCombiPcrRL']))
    canvas.draw_string(x + 18, y + 8, f"{tele['SlipCombiPcrRR']}%", colorbyrange(COLBGR,COLBYL,COLBRD,SLIPCOMBITHRESHOLD_LOW,SLIPCOMBITHRESHOLD_HIGH,tele['SlipCombiPcrRR']))


def draw_alignment_analyzer(canvas, tele, x=80, y=3):
    canvas.draw_string(x, y, " [ DYNAMIC CAMBER & ALIGNMENT ]", COLWHT)
    
    # 1. Grab your newly calculated absolute percentage values
    sa_fl = tele['SlipAnglePcrFL']
    sa_fr = tele['SlipAnglePcrFR']
    sa_rl = tele['SlipAnglePcrRL']
    sa_rr = tele['SlipAnglePcrRR']
    
    # 2. Extract current raw core temperatures
    t_fl = tele['TireTempFL']
    t_fr = tele['TireTempFR']
    t_rl = tele['TireTempRL']
    t_rr = tele['TireTempRR']
    
    # 3. Calculate "Thermal Work Index" (Heat generated per unit of lateral slip)
    # This detects if a tire is generating excessive friction heat without matching lateral grip
    def calc_camber_efficiency(temp, slip_angle):
        if slip_angle < 10:  # Ignore straightaways to prevent dividing by zero
            return 0.0
        return temp / slip_angle

    eff_fl = calc_camber_efficiency(t_fl, sa_fl)
    eff_fr = calc_camber_efficiency(t_fr, sa_fr)
    eff_rl = calc_camber_efficiency(t_rl, sa_rl)
    eff_rr = calc_camber_efficiency(t_rr, sa_rr)
    
    # 4. Determine which side of the car is being compressed into the asphalt
    # Forza suspension travel ranges from 0.0 (fully extended) to 1.0 (slammed/compressed)
    is_cornering_hard = max(sa_fl, sa_fr, sa_rl, sa_rr) > 50 # Over 50% lateral slip limit
    
    # Analyze Front Axle Alignment
    canvas.draw_string(x + 2, y + 2, f"FL Temp: {t_fl:3.0f}°F | Eff: {eff_fl:.1f}", COLBCY if sa_fl < 90 else COLRED)
    canvas.draw_string(x + 2, y + 3, f"FR Temp: {t_fr:3.0f}°F | Eff: {eff_fr:.1f}", COLBCY if sa_fr < 90 else COLRED)
    
    # Analyze Rear Axle Alignment
    canvas.draw_string(x + 2, y + 5, f"RL Temp: {t_rl:3.0f}°F | Eff: {eff_rl:.1f}", COLBYL if sa_rl < 90 else COLRED)
    canvas.draw_string(x + 2, y + 6, f"RR Temp: {t_rr:3.0f}°F | Eff: {eff_rr:.1f}", COLBYL if sa_rr < 90 else COLRED)
    
    # 5. Live Setup Diagnostics Display
    canvas.draw_string(x + 2, y + 8, "DIAGNOSTIC STATUS:", COLWHT)
    if is_cornering_hard:
        # Check if the loaded outside tires are spiking in temp significantly faster than inside tires
        if tele['SuspensionTravelFL'] > tele['SuspensionTravelFR']: # Turning Right (Left side loaded)
            loaded_temp_front, unloaded_temp_front = t_fl, t_fr
            loaded_temp_rear, unloaded_temp_rear = t_rl, t_rr
            active_side = "LEFT SIDE LOADED"
        else: # Turning Left (Right side loaded)
            loaded_temp_front, unloaded_temp_front = t_fr, t_fl
            loaded_temp_rear, unloaded_temp_rear = t_rr, t_rl
            active_side = "RIGHT SIDE LOADED"
            
        canvas.draw_string(x + 2, y + 9, f"Status: {active_side}", COLYEL)
        
        # FRONT CAMBER ASSESSMENT
        if loaded_temp_front > (unloaded_temp_front + 40):
            canvas.draw_string(x + 2, y + 10, "FRONT: Overheating outside edge. Add -Camber.", COLRED)
        elif loaded_temp_front < (unloaded_temp_front + 10) and loaded_temp_front > 160:
            canvas.draw_string(x + 2, y + 10, "FRONT: Inside dragging hard. Reduce -Camber.", COLMAG)
        else:
            canvas.draw_string(x + 2, y + 10, "FRONT: Contact patch uniform.", COLGRN)
            
        # REAR CAMBER ASSESSMENT
        if loaded_temp_rear > (unloaded_temp_rear + 35):
            canvas.draw_string(x + 2, y + 11, "REAR:  Tires rolling over. Add -Camber.", COLRED)
        else:
            canvas.draw_string(x + 2, y + 11, "REAR:  Traction footprint stable.", COLGRN)
    else:
        canvas.draw_string(x + 2, y + 9, "Status: Rolling Straight (Gathering Data...)", COLGRN)


def draw_camber_tuner_suggestions(canvas, tele, x=80, y=15):
    canvas.draw_string(x, y, " [ GARAGE ALIGNMENT RECOMMENDATIONS ]", COLWHT)
    
    # Check the front axle while experiencing high cornering stress
    sa_front_max = max(tele['SlipAnglePcrFL'], tele['SlipAnglePcrFR'])
    t_fl, t_fr = tele['TireTempFL'], tele['TireTempFR']
    
    if sa_front_max > 75:  # Active high-load cornering validation check
        if tele['SlipAnglePcrFL'] > tele['SlipAnglePcrFR']:  
            # Car turning Left -> Right tire is loaded outside tire
            outside_t, inside_t = t_fr, t_fl
            axle_label = "FRONT AXLE: CORNERING LEFT"
        else:
            # Car turning Right -> Left tire is loaded outside tire
            outside_t, inside_t = t_fl, t_fr
            axle_label = "FRONT AXLE: CORNERING RIGHT"
            
        delta_t = outside_t - inside_t
        canvas.draw_string(x + 2, y + 2, f"Status: {axle_label}", COLYEL)
        canvas.draw_string(x + 2, y + 3, f"Outside Delta: {delta_t:3.1f}°F", COLBCY)
        
        # Output actionable garage setup directions
        if delta_t < 15.0:
            canvas.draw_string(x + 2, y + 5, "SUGGESTION: ADD MORE NEGATIVE CAMBER", COLRED)
            canvas.draw_string(x + 2, y + 6, "-> Outside tire is rolling onto shoulder.", COLWHT)
        elif delta_t > 45.0:
            canvas.draw_string(x + 2, y + 5, "SUGGESTION: REDUCE NEGATIVE CAMBER", COLMAG)
            canvas.draw_string(x + 2, y + 6, "-> Inside edge is gouging pavement.", COLWHT)
        else:
            canvas.draw_string(x + 2, y + 5, "SUGGESTION: CAMBER ALIGNMENT OPTIMAL", COLGRN)
            canvas.draw_string(x + 2, y + 6, "-> Contact footprint is working flat.", COLWHT)
    else:
        canvas.draw_string(x + 2, y + 2, "Status: Gathering lateral load states...", COLGRN)
        canvas.draw_string(x + 2, y + 4, "-> Drive hard through a long sweeper.", COLWHT)



def draw_orientation_block(canvas, tele, x=0, y=10):
    dPitch = rad2deg(tele["Pitch"])
    dRoll = rad2deg(tele["Roll"])
    dYaw = rad2deg(tele["Yaw"])
    direction_str = yaw2direction(dYaw)
    
    canvas.draw_string(x, y, " [ CAR ORIENTATION ]", COLWHT)
    canvas.draw_string(x + 2, y + 1, f"Yaw:   {dYaw:6.2f}° ({direction_str})", COLBYL)
    canvas.draw_string(x + 2, y + 2, f"Pitch: {dPitch:6.2f}°", COLBYL)
    canvas.draw_string(x + 2, y + 3, f"Roll:  {dRoll:6.2f}°", COLBYL)
    canvas.draw_string(x + 2, y + 4, f"Lap:   {tele['LapNumber']}", COLWHT)
    canvas.draw_string(x + 2, y + 5, f"Pos:   {tele['RacePosition']}", COLWHT)

def draw_orientation_vector(canvas, tele, x=28, y=13):
    dx = math.sin(tele["Yaw"])
    dy = math.cos(tele["Yaw"])
    rdx=round(dx * 2)
    rdy=round(dy * 2)
    Ntarget_x = x + rdx
    Ntarget_y = y - rdy
    Starget_x = x - rdx
    Starget_y = y + rdy
    Etarget_x = x - rdy
    Etarget_y = y - rdx
    Wtarget_x = x + rdy
    Wtarget_y = y + rdx
    canvas.draw_string(x, y, "o", COLWHT)
    canvas.draw_string(x, y-1, "▲", COLBBL)
    if (Ntarget_x, Ntarget_y) != (x, y):
        canvas.draw_string(Ntarget_x, Ntarget_y, "N", COLRED)    
    if (Starget_x, Starget_y) != (x, y):
        canvas.draw_string(Starget_x, Starget_y, "S", COLBLU)
    if (Etarget_x, Etarget_y) != (x, y):
        canvas.draw_string(Etarget_x, Etarget_y, "E", COLBYL)
    if (Wtarget_x, Wtarget_y) != (x, y):
        canvas.draw_string(Wtarget_x, Wtarget_y, "W", COLBGR)

def draw_speed_history_graph(canvas, speed_history, max_observed_speed, x=0, y=18):
    canvas.draw_string(x, y, f"[ SPEED HISTORY - MAX OBSERVED: {max_observed_speed:.1f} MPH ]", COLWHT)
    
    graph_height = 10
    for row in range(graph_height, 0, -1):
        row_top = (row / graph_height) * max_observed_speed
        row_bottom = ((row - 1) / graph_height) * max_observed_speed
        row_half = row_bottom + (row_top - row_bottom) * 0.5
        
        for col_idx, val in enumerate(speed_history):
            graph_x = x + 0 + col_idx
            graph_y = y + 1 + (graph_height - row)  # Pushes graph down into rows below the label
            
            grphcolor = COLBCY
            if (glbcntr + graph_x) % 10 == 0:  # Add a vertical grid line every 10 columns
                grphcolor = COLBRD
            if val > row_top:
                canvas.draw_string(graph_x, graph_y+1, "▒", grphcolor)
            elif val >= row_bottom:
                if val >= row_half:
                    canvas.draw_string(graph_x, graph_y+1, "█", grphcolor)
                else:
                    canvas.draw_string(graph_x, graph_y+1, "▄", grphcolor)


# --- CENTRALIZED DRAWING FUNCTION ---
def draw_terminal(canvas, tele, speed_history, max_observed_speed):
    canvas.clear()
    
    # Pre-calculate UI display values
    speed_mph = tele["Speed"] * 2.23694
    gear_map = {0: "R", 11: "N"}
    gear_display = gear_map.get(tele["Gear"], str(tele["Gear"]))
    
    dPitch = rad2deg(tele["Pitch"])
    dRoll = rad2deg(tele["Roll"])
    dYaw = rad2deg(tele["Yaw"])
    direction_str = yaw2direction(dYaw)
    
    # 0. boundary
    draw_boundary_box(canvas, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, COLBGR)

    # 1. Title Block
    draw_title_block(canvas, tele, 2, 0)
    
    # 2. Telemetry Text Data
    draw_telemetry_text(canvas, tele, gear_display, 2, 3)
    
    # 3. Input Controls Bars
    draw_input_bars(canvas, tele, 2, 7)
    
    # 4. Car Silhouette Blit
    draw_car_silhouette(canvas, tele, 42, 2)
    
    # 5. Orientation Info Block
    draw_orientation_block(canvas, tele, 2, 10)

    
    # 6. Orientation Vector Mini-Widget
    draw_orientation_vector(canvas, tele, 28, 13)
        
    # 7. Speed History Graph with Top-Capping Logic
    draw_speed_history_graph(canvas, speed_history, max_observed_speed, 2, 18)

    # 8. Tire Slip Info (Optional)
    draw_tire_slip_info(canvas, tele, 48, 9)

    # 9. Experimental Dynamic Camber & Alignment Analyzer (Optional)
    draw_alignment_analyzer(canvas, tele, 80, 9)

    #10. Garage Setup Suggestions Based on Thermal Analysis (Optional)
    draw_camber_tuner_suggestions(canvas, tele, 80, 23)

    # Render frame buffer directly to stdout
    print(canvas.render(), end="")


if __name__ == "__main__":
    # --- INITIALIZATION & MAIN NETWORK LOOP ---
    UDP_IP = "0.0.0.0"
    UDP_PORT = 9999
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    graph_width = 75  # Number of historical points to show in the speed graph
    speed_history = collections.deque([0.0] * graph_width, maxlen=graph_width)
    max_observed_speed = 100.0

    canvas = TerminalCanvas(CANVAS_WIDTH, CANVAS_HEIGHT)
    os.system('clear')
    print("\033[?25l")  # Hide terminal cursor

    try:
        while True:
            raw_data, addr = sock.recvfrom(1024)
            tele = parse_packet(raw_data)
            if not tele: continue
            
            # Track speed values inside global processing arrays
            speed_mph = tele["Speed"] * 2.23694
            speed_history.append(speed_mph)
            glbcntr+=1
            if speed_mph > max_observed_speed:
                max_observed_speed = speed_mph

            SlipRatioPcrFL=abs(int(tele['TireSlipRatioFL']*100))
            SlipRatioPcrFR=abs(int(tele['TireSlipRatioFR']*100))
            SlipRatioPcrRL=abs(int(tele['TireSlipRatioRL']*100))
            SlipRatioPcrRR=abs(int(tele['TireSlipRatioRR']*100))
            SlipAnglePcrFL=abs(int(tele['TireSlipAngleFL']*100))
            SlipAnglePcrFR=abs(int(tele['TireSlipAngleFR']*100))
            SlipAnglePcrRL=abs(int(tele['TireSlipAngleRL']*100))
            SlipAnglePcrRR=abs(int(tele['TireSlipAngleRR']*100))
            SlipCombiPcrFL=abs(int(tele['TireCombinedSlipFL']*100))
            SlipCombiPcrFR=abs(int(tele['TireCombinedSlipFR']*100))
            SlipCombiPcrRL=abs(int(tele['TireCombinedSlipRL']*100))
            SlipCombiPcrRR=abs(int(tele['TireCombinedSlipRR']*100))
            tele['SlipRatioPcrFL']=SlipRatioPcrFL
            tele['SlipRatioPcrFR']=SlipRatioPcrFR
            tele['SlipRatioPcrRL']=SlipRatioPcrRL
            tele['SlipRatioPcrRR']=SlipRatioPcrRR
            tele['SlipAnglePcrFL']=SlipAnglePcrFL
            tele['SlipAnglePcrFR']=SlipAnglePcrFR
            tele['SlipAnglePcrRL']=SlipAnglePcrRL
            tele['SlipAnglePcrRR']=SlipAnglePcrRR
            tele['SlipCombiPcrFL']=SlipCombiPcrFL
            tele['SlipCombiPcrFR']=SlipCombiPcrFR
            tele['SlipCombiPcrRL']=SlipCombiPcrRL
            tele['SlipCombiPcrRR']=SlipCombiPcrRR
            # Draw everything through our decoupled graphics state machine
            draw_terminal(canvas, tele, speed_history, max_observed_speed)

    except KeyboardInterrupt:
        print("\033[?25h")  # Restore cursor
        print("\nDashboard closed.")
        sock.close()
