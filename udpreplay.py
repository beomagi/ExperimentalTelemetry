#!/usr/bin/env python3
import socket
import struct
import time
import sys

RECORD_IP = "0.0.0.0"
RECORD_PORT = 9999
PLAYBACK_IP = "127.0.0.1"
PLAYBACK_PORT = 9999


##--------- FH6 Specific Code ---------##
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

def parse_packet(data):
    if len(data) < 324: return None
    return dict(zip(FORZA_FIELDS, struct.unpack(FORZA_FORMAT, data[:324])))
##--------- FH6 Specific Code ---------##


args=sys.argv[1:]
if len(args) < 1:
    print("Usage: udpreplay.py [-rec filename] [-play filename] [-IP IP] [-repeat] [-port port] [-dest-port port]")
    sys.exit(1)
repeat = False

def draw_recording_status(elapsed_time, packets, bytes):
    """ draw a simple recording status - time, packets, bytes """

    print(f"\rRecording: | Elapsed: {elapsed_time:.2f}s | Packets: {packets} | Bytes: {bytes}", end="")


def udp_record(filename):
    countdown("Recording")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((RECORD_IP, RECORD_PORT))
    start_time = time.time()
    try:
        with open(filename, "wb") as f:
            while True:
                data, addr = sock.recvfrom(1024)
                timestamp = time.time()
                f.write(struct.pack("d", timestamp))
                f.write(struct.pack("I", len(data)))
                f.write(data)
                elapsed_time = timestamp - start_time
                draw_recording_status(elapsed_time, f.tell() // 1028, f.tell())
    finally:
        sock.close()


def load_udp_data(filename):
    data_list = []
    with open(filename, "rb") as f:
        while True:
            timestamp_bytes = f.read(8)
            if not timestamp_bytes:
                break
            timestamp = struct.unpack("d", timestamp_bytes)[0]
            data_len = struct.unpack("I", f.read(4))[0]
            data = f.read(data_len)
            data_list.append((timestamp, data))
    return data_list


def play_total_time(data_list):
    """ determine the total time of the recorded data """
    if not data_list:
        return 0
    return data_list[-1][0] - data_list[0][0]


def draw_progress_bar(total_time, elapsed_time, speed_mph=0):
    """ draw a simple progress bar in the terminal """
    bar_length = 50
    progress = min(elapsed_time / total_time, 1.0)
    filled_length = int(bar_length * progress)
    bar = "#" * filled_length + "-" * (bar_length - filled_length)
    print(f"\rProgress: |{bar}| {progress:.2%} Elapsed: {elapsed_time:.2f}s Speed: {speed_mph:.2f} MPH", end="")


def udp_play(data_list):
    dest = (PLAYBACK_IP, PLAYBACK_PORT)
    playtime = play_total_time(data_list)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        datapoints = len(data_list)
        for index in range(datapoints):
            timestamp, data = data_list[index]
            tele = parse_packet(data)
            if tele is None:
                speed_mph = 0
            else:
                speed_mph = tele["Speed"] * 2.23694                
            next_timestamp = data_list[index + 1][0] if index + 1 < datapoints else timestamp
            sleeptime = next_timestamp - timestamp
            if sleeptime > 0:
                time.sleep(sleeptime)
            try:
                sock.sendto(data, dest)
            except ConnectionRefusedError:
                pass
            draw_progress_bar(playtime, timestamp - data_list[0][0], speed_mph)
    time.sleep(1)  # ensure all packets are sent before exiting


def countdown(inittext="Starting",seconds=5):
    """ simple countdown timer for user feedback """
    for i in range(seconds, 0, -1):
        print(f"\r{inittext} in {i} seconds... ", end="")
        time.sleep(1)
    print("\r" + inittext + " now!            ")

if __name__ == "__main__":

    if "-rec" in args:
        filename = args[args.index("-rec") + 1]
        mode = "rec"
    elif "-play" in args:
        filename = args[args.index("-play") + 1]
        mode = "play"
    if "-repeat" in args:
        repeat = True
    if "-port" in args:
        RECORD_PORT = int(args[args.index("-port") + 1])
    if "-dest-port" in args:
        PLAYBACK_PORT = int(args[args.index("-dest-port") + 1])
    if "-IP" in args:
        PLAYBACK_IP = args[args.index("-IP") + 1]

    if mode == "rec":
        udp_record(filename)
    elif mode == "play":
        while True:
            data_list = load_udp_data(filename)
            udp_play(data_list)
            if not repeat:
                break

    