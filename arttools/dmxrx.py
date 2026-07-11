from machine import UART, Pin
import uos

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio


class AsyncDMXReceiver:
    def __init__(self, uart_id=0, de_pin=5, re_pin=4):
        """
        Simple async DMX receiver
        de_pin: Driver Enable pin on MAX485 (GPIO5/D1)
        re_pin: Receiver Enable pin on MAX485 (GPIO4/D2)
        """
        # Initialize UART for DMX (250000 baud, 8N2)
        self.uart = UART(uart_id, baudrate=250000, bits=8, parity=None, stop=2)

        # Initialize control pins for MAX485
        self.de = Pin(de_pin, Pin.OUT)
        self.re = Pin(re_pin, Pin.OUT)

        # Set MAX485 to receive mode (DE=LOW, RE=LOW)
        self.de.value(0)
        self.re.value(0)

        # Buffer for channels
        self.channels = [0] * 8

    def read_channels(self):
        """
        Simple read: grab whatever data is available and parse it
        Returns list of first 8 channels or None if no data
        """
        if self.uart.any():
            # Read available data
            data = self.uart.read()
            if data and len(data) >= 9:  # start_code + 8 channels
                # DMX format: [start_code, ch1, ch2, ...]
                # Start code is usually 0x00
                if data[0] == 0:
                    self.channels = list(data[1:9])
                    return self.channels
                # If no start code at position 0, try to find it
                elif len(data) >= 8:
                    self.channels = list(data[0:8])
                    return self.channels
        return None

    async def continuous_read(self, callback=None, delay_ms=20):
        """
        Continuously read and print DMX channels (async version)

        Args:
            callback: Optional callback function(channels) called when values change
            delay_ms: Polling interval in milliseconds
        """
        print("DMX Async Receiver Started")
        print("Press Ctrl+C to stop")
        print("-" * 40)

        last_channels = [-1] * 8

        try:
            while True:
                result = self.read_channels()

                if result:
                    # Only process if values changed
                    if result != last_channels:
                        last_channels = result[:]

                        # Call callback if provided
                        if callback:
                            callback(result)

                # Async sleep instead of blocking sleep
                await asyncio.sleep_ms(delay_ms)

        except asyncio.CancelledError:
            print("\nStopped")


async def main():
    """
    Simple async usage example
    """
    # Disconnect UART0 from REPL to stop RX echo
    uos.dupterm(None, 1)

    # Create receiver
    dmx = AsyncDMXReceiver(uart_id=0, de_pin=5, re_pin=4)

    # Give it a moment to settle
    await asyncio.sleep_ms(100)

    # Clear any startup garbage
    if dmx.uart.any():
        _ = dmx.uart.read()

    print("Starting DMX monitoring...")

    # Example callback for channel 1
    def example_callback(channels):
        print(f"CH1: {channels[0]}")

    # Continuous monitoring with callback
    await dmx.continuous_read(callback=example_callback, delay_ms=50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")
