from machine import UART, Pin

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio


class AsyncDMXReceiver:
    """DMX-512 receiver using ESP32 UART BREAK detection for frame alignment."""

    def __init__(self, uart_id=2, de_pin=4, re_pin=5, tx_pin=17, rx_pin=16, max_channels=32):
        self.uart = UART(
            uart_id,
            baudrate=250000,
            bits=8,
            parity=None,
            stop=2,
            tx=tx_pin,
            rx=rx_pin,
            rxbuf=1024,
        )

        self.de = Pin(de_pin, Pin.OUT, value=0)
        self.re = Pin(re_pin, Pin.OUT, value=0)

        self.max_channels = max_channels
        # ESP-IDF UART pushes a framing-error 0x00 into the buffer at BREAK detection,
        # so a valid frame is: [0x00 artifact, 0x00 start code, ch1..chN, ...trailing].
        self._min_frame_len = max_channels + 2
        self.channels = [0] * max_channels
        self._latest_frame = None
        self._frame_count = 0

        if not hasattr(UART, "IRQ_BREAK"):
            raise RuntimeError(
                "UART.IRQ_BREAK not available in this MicroPython build — "
                "upgrade firmware or use a polling-based DMX parser."
            )

        self.uart.irq(handler=self._on_break, trigger=UART.IRQ_BREAK)

    def _on_break(self, uart):
        """Fires on DMX BREAK — the buffer holds the frame that just ended."""
        data = uart.read()
        if not data or len(data) < self._min_frame_len:
            return
        if data[0] != 0x00 or data[1] != 0x00:
            return

        channels = data[2 : 2 + self.max_channels]
        if len(channels) >= self.max_channels:
            self._latest_frame = list(channels)
            self._frame_count += 1

    def read_channels(self):
        """Return the most recent complete frame, or None if none pending."""
        frame = self._latest_frame
        if frame is None:
            return None
        self._latest_frame = None
        self.channels = frame
        return frame

    async def continuous_read(self, callback=None, delay_ms=20):
        print("DMX Async Receiver Started (BREAK-triggered)")
        last = None
        try:
            while True:
                frame = self.read_channels()
                if frame is not None and frame != last:
                    last = frame[:]
                    if callback:
                        callback(frame)
                await asyncio.sleep_ms(delay_ms)
        except asyncio.CancelledError:
            print("\nStopped")
