#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import struct

# Structure map matching Forza V2 / Horizon extended telemetry format
# Total size: 324 bytes
# Format breakdown:
# <   : Little-endian
# i   : S32 (IsRaceOn)
# I   : U32 (TimestampMS)
# 12f : F32 x 12 (Engine RPMs, Accel, Vel, Angular Vel)
# 3f  : F32 x 3  (Yaw, Pitch, Roll)
# 4f  : F32 x 4  (Suspension Travel FL, FR, RL, RR)
# 4f  : F32 x 4  (Tire Slip Ratio FL, FR, RL, RR)
# 4f  : F32 x 4  (Wheel Rotation Speed)
# 4i  : S32 x 4  (Wheel On Rumble Strip)
# 4i  : S32 x 4  (Wheel In Puddle)
# 4f  : F32 x 4  (Surface Rumble)
# 4f  : F32 x 4  (Tire Slip Angle)
# 4f  : F32 x 4  (Tire Combined Slip)
# 4f  : F32 x 4  (Suspension Travel Meters)
# 5i  : S32 x 5  (CarOrdinal, CarClass, CarPI, Drivetrain, NumCylinders)
# I   : U32      (CarGroup)
# 2f  : F32 x 2  (SmashableVelDiff, SmashableMass)
# 3f  : F32 x 3  (Position X, Y, Z)
# 3f  : F32 x 3  (Speed, Power, Torque)
# 4f  : F32 x 4  (Tire Temp)
# 3f  : F32 x 3  (Boost, Fuel, DistanceTraveled)
# 4f  : F32 x 4  (BestLap, LastLap, CurrentLap, CurrentRaceTime)
# H   : U16      (LapNumber)
# 5B  : U8 x 5   (RacePosition, Accel, Brake, Clutch, HandBrake)
# B   : U8       (Gear)
# 3b  : S8 x 3   (Steer, NormalizedDrivingLine, NormalizedAIBrakeDifference)
# x   : 1-byte padding to align the struct to exactly 324 bytes

FORZA_FORMAT = '<iI12f3f4f4f4f4i4i4f4f4f4f5iI2f3f3f4f3f4fH5BB3bx'

# Key names in the exact sequence of the packet structure
FORZA_FIELDS = [
    "IsRaceOn", "TimestampMS",
    "EngineMaxRpm", "EngineIdleRpm", "CurrentEngineRpm",
    "AccelerationX", "AccelerationY", "AccelerationZ",
    "VelocityX", "VelocityY", "VelocityZ",
    "AngularVelocityX", "AngularVelocityY", "AngularVelocityZ",
    "Yaw", "Pitch", "Roll",
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
    "CarGroup", "SmashableVelDiff", "SmashableMass",
    "PositionX", "PositionY", "PositionZ",
    "Speed", "Power", "Torque",
    "TireTempFL", "TireTempFR", "TireTempRL", "TireTempRR",
    "Boost", "Fuel", "DistanceTraveled",
    "BestLap", "LastLap", "CurrentLap", "CurrentRaceTime",
    "LapNumber", "RacePosition", "Accel", "Brake", "Clutch", "HandBrake",
    "Gear", "Steer", "NormalizedDrivingLine", "NormalizedAIBrakeDifference"
]

def parse_forza_packet(raw_data: bytes) -> dict:
    """Parses raw UDP packet bytes into a readable dictionary."""
    if len(raw_data) < 324:
        return {}
    
    # Slice first 324 bytes to discard any erratic trailing network data
    unpacked = struct.unpack(FORZA_FORMAT, raw_data[:324])
    
    # Zip the field names with unpacked values into a dictionary
    return dict(zip(FORZA_FIELDS, unpacked))


import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 9999

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print("Telemetry loop active...")

try:
    while True:
        data, addr = sock.recvfrom(1024)
        telemetry = parse_forza_packet(data)
        
        if telemetry and telemetry["IsRaceOn"] == 1:
            # Conversion math example
            speed_mph = telemetry["Speed"] * 2.23694
            rpm = telemetry["CurrentEngineRpm"]
            gear = telemetry["Gear"]
            
            print(f"Gear: {gear} | RPM: {rpm:.0f} | Speed: {speed_mph:.1f} MPH", end="\r")
            
except KeyboardInterrupt:
    sock.close()





##################################################
"""  Packet Documentation
Output Structure
Type Notes
[Letter][Number]
The letter defines the type from one of the following:
S -- Signed Integer
U -- Unsigned Integer
F -- Floating Point
The number defines the amount of bits used.
Examples:
S8 is a signed byte with potential values between -128 and 127.
F32 is a 32-bit floating point number, equivalent to float/single.
U32 is a 32-bit unsigned integer.
Packet Format
Total packet size: 324 bytes.

// = 1 when race is on. = 0 when in menus/race stopped.
S32 IsRaceOn;

// Can overflow to 0 eventually
U32 TimestampMS;

// Engine RPM values
F32 EngineMaxRpm;
F32 EngineIdleRpm;
F32 CurrentEngineRpm;

// In the car's local space; X = right, Y = up, Z = forward
F32 AccelerationX;
F32 AccelerationY;
F32 AccelerationZ;

// In the car's local space; X = right, Y = up, Z = forward
F32 VelocityX;
F32 VelocityY;
F32 VelocityZ;

// Angular velocity in the car's local space (rad/s); X = pitch, Y = yaw, Z = roll
F32 AngularVelocityX;
F32 AngularVelocityY;
F32 AngularVelocityZ;

// Car orientation (radians)
F32 Yaw;
F32 Pitch;
F32 Roll;

// Suspension travel normalized: 0.0f = max stretch; 1.0 = max compression
F32 NormalizedSuspensionTravelFrontLeft;
F32 NormalizedSuspensionTravelFrontRight;
F32 NormalizedSuspensionTravelRearLeft;
F32 NormalizedSuspensionTravelRearRight;

// Tire normalized slip ratio, = 0 means 100% grip and |ratio| > 1.0 means loss of grip.
F32 TireSlipRatioFrontLeft;
F32 TireSlipRatioFrontRight;
F32 TireSlipRatioRearLeft;
F32 TireSlipRatioRearRight;

// Wheel rotation speed radians/sec.
F32 WheelRotationSpeedFrontLeft;
F32 WheelRotationSpeedFrontRight;
F32 WheelRotationSpeedRearLeft;
F32 WheelRotationSpeedRearRight;

// = 1 when wheel is on rumble strip, = 0 when off.
S32 WheelOnRumbleStripFrontLeft;
S32 WheelOnRumbleStripFrontRight;
S32 WheelOnRumbleStripRearLeft;
S32 WheelOnRumbleStripRearRight;

// = 1 when wheel is in a puddle, = 0 when not.
S32 WheelInPuddleFrontLeft;
S32 WheelInPuddleFrontRight;
S32 WheelInPuddleRearLeft;
S32 WheelInPuddleRearRight;

// Non-dimensional surface rumble values passed to controller force feedback
F32 SurfaceRumbleFrontLeft;
F32 SurfaceRumbleFrontRight;
F32 SurfaceRumbleRearLeft;
F32 SurfaceRumbleRearRight;

// Tire normalized slip angle, = 0 means 100% grip and |angle| > 1.0 means loss of grip.
F32 TireSlipAngleFrontLeft;
F32 TireSlipAngleFrontRight;
F32 TireSlipAngleRearLeft;
F32 TireSlipAngleRearRight;

// Tire normalized combined slip, = 0 means 100% grip and |slip| > 1.0 means loss of grip.
F32 TireCombinedSlipFrontLeft;
F32 TireCombinedSlipFrontRight;
F32 TireCombinedSlipRearLeft;
F32 TireCombinedSlipRearRight;

// Actual suspension travel in meters
F32 SuspensionTravelMetersFrontLeft;
F32 SuspensionTravelMetersFrontRight;
F32 SuspensionTravelMetersRearLeft;
F32 SuspensionTravelMetersRearRight;

// Unique ID of the car make/model
S32 CarOrdinal;

// Between 0 (D -- worst cars) and 7 (X class -- best cars) inclusive
S32 CarClass;

// Between 100 (worst car) and 999 (best car) inclusive
S32 CarPerformanceIndex;

// 0 = FWD, 1 = RWD, 2 = AWD
S32 DrivetrainType;

// Number of cylinders in the engine
S32 NumCylinders;

// Car group identifier
U32 CarGroup;

// Velocity loss from smashable object collision (m/s)
F32 SmashableVelDiff;

// Mass of recently hit smashable object (kg)
F32 SmashableMass;

// Position in world space (meters)
F32 PositionX;
F32 PositionY;
F32 PositionZ;

// Speed in meters per second
F32 Speed;

// Power in watts
F32 Power;

// Torque in newton-meters
F32 Torque;

// Tire temperature
F32 TireTempFrontLeft;
F32 TireTempFrontRight;
F32 TireTempRearLeft;
F32 TireTempRearRight;

// Turbo/supercharger boost (PSI above atmospheric)
F32 Boost;

// Fuel level (0.0 = empty, 1.0 = full)
F32 Fuel;

// Total distance traveled (meters)
F32 DistanceTraveled;

// Lap times (seconds); 0.0 if not applicable
F32 BestLap;
F32 LastLap;
F32 CurrentLap;

// Total race time (seconds since driving started)
F32 CurrentRaceTime;

// Number of laps completed
U16 LapNumber;

// Current race position
U8 RacePosition;

// Player inputs (0 to 255)
U8 Accel;
U8 Brake;
U8 Clutch;
U8 HandBrake;

// Current gear
U8 Gear;

// Steering input (-127 = full left, 0 = center, 127 = full right)
S8 Steer;

// Normalized driving line position (-127 to 127)
S8 NormalizedDrivingLine;

// Normalized AI braking difference (-127 to 127)
S8 NormalizedAIBrakeDifference;

"""