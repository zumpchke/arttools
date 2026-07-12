"""
mDNS Responder for MicroPython with asyncio support

To use as a module in your code:
    from mdns_responder import MDNSResponder
    import uasyncio as asyncio
    
    async def main():
        mdns = MDNSResponder("myesp")
        
        # Start as a background task
        asyncio.create_task(mdns.start())
        
        # Your other code here
        while True:
            await asyncio.sleep(1)
    
    asyncio.run(main())

To run directly: just import or execute this file
"""

import uasyncio as asyncio
import socket
import struct
import select
import network

MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353
ADVERTISE_INTERVAL = 30  # seconds

def inet_aton(ip_str):
    """Minimal replacement for socket.inet_aton for ESP8266."""
    parts = ip_str.split('.')
    return bytes([int(p) & 0xFF for p in parts])

def get_ip():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)
    return wlan.ifconfig()[0]

class MDNSResponder:
    def __init__(self, hostname, advertise_interval=ADVERTISE_INTERVAL):
        """
        Initialize mDNS responder
        
        Args:
            hostname: Hostname without .local suffix (e.g., "myesp")
            advertise_interval: Seconds between advertisements (default: 30)
        """
        self.hostname = hostname
        self.advertise_interval = advertise_interval
        self.ip = get_ip()
        # Prebuild hostname label with correct length
        hostname_bytes = hostname.encode()
        self.name = bytes([len(hostname_bytes)]) + hostname_bytes + b'\x05local\x00'
        self.sock = None
        self.running = False
        
    def setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Join multicast group for receiving queries
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                 inet_aton(MDNS_ADDR) + inet_aton(self.ip))
        except Exception:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                 inet_aton(MDNS_ADDR) + b'\x00\x00\x00\x00')
        
        self.sock.bind(("0.0.0.0", MDNS_PORT))
        self.sock.setblocking(False)
        
    def build_response(self, transaction_id=0):
        """Build mDNS response packet"""
        # Header: transaction_id, flags=0x8400 (response + authoritative),
        # qdcount=0, ancount=1, nscount=0, arcount=0
        header = struct.pack("!HHHHHH", transaction_id, 0x8400, 0, 1, 0, 0)
        # Resource record: name + type=A, class=IN+cache-flush, ttl=120, length=4, IP
        rr = self.name + struct.pack("!HHIH", 1, 0x8001, 120, 4) + inet_aton(self.ip)
        return header + rr
    
    async def listen_queries(self):
        """Listen for mDNS queries and respond via unicast"""
        poll = select.poll()
        poll.register(self.sock, select.POLLIN)
        
        print("mDNS: Listening for queries on", self.hostname + ".local at", self.ip)
        
        while self.running:
            events = poll.poll(10)  # 10ms poll
            if events:
                try:
                    data, addr = self.sock.recvfrom(512)
                    # Check if query contains our hostname
                    if self.name in data:
                        print("mDNS: Query for", self.hostname + ".local from", addr)
                        
                        # Extract transaction ID from query
                        tid = struct.unpack("!H", data[:2])[0]
                        packet = self.build_response(tid)
                        
                        # Send unicast response
                        self.sock.sendto(packet, addr)
                        print("mDNS: Sent unicast response ->", addr)
                except Exception as e:
                    print("mDNS recv error:", e)
            
            await asyncio.sleep_ms(10)
    
    async def advertise_periodic(self):
        """Periodically send multicast advertisements"""
        await asyncio.sleep(5)  # Wait 5s before first advertisement
        
        while self.running:
            try:
                packet = self.build_response(0)
                self.sock.sendto(packet, (MDNS_ADDR, MDNS_PORT))
                print("mDNS: Advertisement sent for", self.hostname + ".local")
            except Exception as e:
                print("mDNS advertise error:", e)
            
            await asyncio.sleep(self.advertise_interval)
    
    async def start(self):
        """Start both query listener and periodic advertiser"""
        if self.running:
            print("mDNS: Already running")
            return
            
        self.running = True
        self.setup_socket()
        
        print("mDNS: Started for", self.hostname + ".local")
        
        # Run both tasks concurrently
        try:
            await asyncio.gather(
                self.listen_queries(),
                self.advertise_periodic()
            )
        except asyncio.CancelledError:
            print("mDNS: Stopped")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the mDNS responder"""
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None

# Run directly when executed
def start():
	async def main():
	    mdns = MDNSResponder("myesp")
	    await mdns.start()
	
	try:
	    asyncio.run(main())
	except KeyboardInterrupt:
	    print("\nProgram terminated")
