import can

# Super simple CAN listener for testing purpose.

bus = can.Bus(
    interface='slcan',
    channel='COM9',
    bitrate=500000
)

print("Listening on CAN bus... Press Ctrl+C to stop.")

try:
    while True:
        msg = bus.recv(1.0)
        if msg is not None:
            print(msg)
except KeyboardInterrupt:
    print("Stopped.")