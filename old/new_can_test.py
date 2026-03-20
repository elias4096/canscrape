import can

print("Opening CANable...")

try:
    bus = can.Bus(
        interface="slcan",
        channel="COM3",
        bitrate=500000,
        ttyBaudrate=115200,
    )
except Exception as e:
    print("Failed to open CAN interface:", e)
    raise

print("Listening on CAN bus... Press Ctrl+C to stop.")

try:
    while True:
        msg = bus.recv(1.0)
        if msg is not None:
            print(msg)

except KeyboardInterrupt:
    print("Stopped.")