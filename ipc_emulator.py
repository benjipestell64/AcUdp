"""
Emulates the TwinCAT IPC for bench testing the AC UDP interface without a motion platform.

Receives the telemetry packet from the data source (decoded with the packet spec, e.g. 238 bytes for DMG-1)
and sends the controller packet back at a fixed rate (all zeros unless overridden in config).

    python ipc_emulator.py                       GUI
    python ipc_emulator.py --headless --duration 10
    python ipc_emulator.py --selftest            loopback test, no network needed
    python ipc_emulator.py --set bind_ip=0.0.0.0 override any config key
"""
import argparse
import copy
import json
import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

from ac_udp.packet_spec import load_packet_spec

CONFIG_FILE = "ipc_emulator.json"

DEFAULT_CONFIG = {
    "packet_spec": "packets/DMG-1.json",
    "bind_ip": "192.168.0.1",     # IPC address (this PC). Use 0.0.0.0 to listen on every adapter
    "rx_port": 10000,             # Telemetry from the data source
    "tx_ip": "192.168.0.2",       # Data source (Speedgoat / AC PC)
    "tx_port": 10010,             # Controller packet back to the data source
    "tx_rate_hz": 100,
    "tx_values": {},              # Optional fixed values for the controller packet, e.g. {"gLongChassis": 1.0}
    "console": {"enabled": True, "level": "INFO"},
    "logging": {"file": "logs/ipc_emulator.log", "level": "DEBUG"},
    "gui": {"width": 900, "height": 900, "fast_update_hz": 30, "slow_update_hz": 4, "plot_seconds": 10,
            "spacing": 8},
}

log = logging.getLogger("ipc_emulator")


# ---------------------------------------------------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------------------------------------------------

def merge_defaults(cfg, defaults):
    """Fill missing keys from defaults, recursively. Returns True if anything was added."""
    changed = False
    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = copy.deepcopy(value)
            changed = True
        elif isinstance(value, dict) and isinstance(cfg[key], dict) and key != "tx_values":
            changed |= merge_defaults(cfg[key], value)
    return changed


def load_config(path, overrides):
    cfg = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    if merge_defaults(cfg, DEFAULT_CONFIG) or not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    # --set a.b=value overrides (value parsed as JSON where possible, else kept as a string)
    for item in overrides:
        key, _, raw = item.partition("=")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        node = cfg
        *parents, leaf = key.split(".")
        for p in parents:
            node = node[p]
        if leaf not in node:
            raise SystemExit(f"--set: unknown config key '{key}'")
        node[leaf] = value
    return cfg


def setup_logging(cfg):
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s", "%H:%M:%S")
    log_file = cfg["logging"]["file"]
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=2)
    fh.setLevel(cfg["logging"]["level"])
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if cfg["console"]["enabled"] and sys.stdout is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(cfg["console"]["level"])
        sh.setFormatter(fmt)
        log.addHandler(sh)


# ---------------------------------------------------------------------------------------------------------------------
# Core (no GUI imports)
# ---------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Snapshot:
    seq: int = 0
    values: tuple = ()           # Latest decoded telemetry packet (namedtuple), empty until first packet
    rx_count: int = 0
    rx_bad_size: int = 0
    last_bad_size: int = 0
    rx_from: str = "-"
    rx_socket_ok: bool = False
    error: str = ""


class IpcEmulator:
    """Receives telemetry, sends controller packets. Publishes a Snapshot that any front end can poll."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.description, self.rx_spec, self.tx_spec = self._load_specs(cfg["packet_spec"])
        self.tx_packet = self._build_tx_packet(cfg["tx_values"])
        self.snapshot = Snapshot()
        self._running = threading.Event()
        self._threads = []
        self._rx_sock = None
        self._counts = {"rx": 0, "bad": 0, "tx": 0}

    @staticmethod
    def _load_specs(path):
        # The spec is written from the data source's point of view, so its "transmit" is what we receive
        description, source_tx, source_rx = load_packet_spec(path)
        return description, source_tx, source_rx

    def _build_tx_packet(self, overrides):
        unknown = set(overrides) - set(self.tx_spec.tuple._fields)
        if unknown:
            raise ValueError(f"tx_values has unknown fields: {', '.join(sorted(unknown))}")
        values = [overrides.get(name, 0) for name in self.tx_spec.tuple._fields]
        return self.tx_spec.pack(self.tx_spec.tuple(*values))

    def start(self):
        cfg = self.cfg
        log.info("Packet spec: %s (%s)", cfg["packet_spec"], self.description)
        log.info("Expecting %d byte packets on %s:%d", self.rx_spec.size, cfg["bind_ip"], cfg["rx_port"])
        log.info("Sending %d byte packets to %s:%d at %s Hz", self.tx_spec.size, cfg["tx_ip"], cfg["tx_port"],
                 cfg["tx_rate_hz"])

        error = ""
        try:
            self._rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._rx_sock.bind((cfg["bind_ip"], cfg["rx_port"]))
            self._rx_sock.settimeout(0.2)  # So the thread notices stop()
        except OSError as e:
            error = f"Can't bind {cfg['bind_ip']}:{cfg['rx_port']} ({e}). Is this PC set to that IP?"
            log.error(error)
            self._rx_sock = None
        self.snapshot = Snapshot(rx_socket_ok=self._rx_sock is not None, error=error)

        self._running.set()
        self._threads = [threading.Thread(target=self._tx_loop, name="tx", daemon=True)]
        if self._rx_sock:
            self._threads.append(threading.Thread(target=self._rx_loop, name="rx", daemon=True))
        for t in self._threads:
            t.start()

    def stop(self):
        self._running.clear()
        for t in self._threads:
            t.join(timeout=1.0)
        if self._rx_sock:
            self._rx_sock.close()
        log.info("Stopped. rx=%d bad=%d tx=%d", *self._counts.values())

    @property
    def tx_count(self):
        """Packets sent so far. Read live, since the snapshot is only republished when something is received."""
        return self._counts["tx"]

    @property
    def rx_port(self):
        return self._rx_sock.getsockname()[1] if self._rx_sock else None

    def _publish(self, **changes):
        s = self.snapshot
        self.snapshot = Snapshot(
            seq=s.seq + 1,
            values=changes.get("values", s.values),
            rx_count=self._counts["rx"], rx_bad_size=self._counts["bad"],
            last_bad_size=changes.get("last_bad_size", s.last_bad_size),
            rx_from=changes.get("rx_from", s.rx_from), rx_socket_ok=s.rx_socket_ok,
            error=changes.get("error", s.error))

    def _rx_loop(self):
        last_warn = 0.0
        while self._running.is_set():
            try:
                data, addr = self._rx_sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError as e:
                if self._running.is_set():
                    log.error("Receive error: %s", e)
                    self._publish(error=f"Receive error: {e}")
                return
            sender = f"{addr[0]}:{addr[1]}"
            if len(data) != self.rx_spec.size:
                self._counts["bad"] += 1
                if time.monotonic() - last_warn > 2.0:  # Rate limit
                    last_warn = time.monotonic()
                    log.warning("Got %d bytes from %s, expected %d (%d bad so far)",
                                len(data), sender, self.rx_spec.size, self._counts["bad"])
                self._publish(last_bad_size=len(data), rx_from=sender)
                continue
            self._counts["rx"] += 1
            if self._counts["rx"] == 1:
                log.info("First valid packet from %s", sender)
            self._publish(values=self.rx_spec.unpack(data), rx_from=sender)

    def _tx_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        period = 1.0 / self.cfg["tx_rate_hz"]
        target = (self.cfg["tx_ip"], self.cfg["tx_port"])
        next_t = time.perf_counter()
        last_err = 0.0
        while self._running.is_set():
            try:
                sock.sendto(self.tx_packet, target)
                self._counts["tx"] += 1
            except OSError as e:
                if time.monotonic() - last_err > 2.0:
                    last_err = time.monotonic()
                    log.error("Send to %s:%d failed: %s", *target, e)
            next_t += period
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.perf_counter()  # Fell behind; don't try to catch up in a burst
        sock.close()


class RateMeter:
    """Turns a running count into a rate, sampled whenever update() is called."""

    def __init__(self):
        self._last = (time.monotonic(), 0)
        self.rate = 0.0

    def update(self, count):
        now = time.monotonic()
        t0, c0 = self._last
        if now - t0 >= 0.5:
            self.rate = (count - c0) / (now - t0)
            self._last = (now, count)
        return self.rate


# ---------------------------------------------------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------------------------------------------------

def run_headless(cfg, duration):
    emu = IpcEmulator(cfg)
    emu.start()
    rx_rate, tx_rate = RateMeter(), RateMeter()
    t_end = time.monotonic() + duration if duration else None
    try:
        while t_end is None or time.monotonic() < t_end:
            time.sleep(1.0)
            s = emu.snapshot
            log.info("rx %.0f Hz (%d ok, %d bad) from %s | tx %.0f Hz", rx_rate.update(s.rx_count), s.rx_count,
                     s.rx_bad_size, s.rx_from, tx_rate.update(emu.tx_count))
    except KeyboardInterrupt:
        pass
    emu.stop()
    return 0 if emu.snapshot.rx_socket_ok else 1


def run_selftest(cfg):
    """Loopback test: send a known telemetry packet to ourselves and check it decodes, and that tx is the right size."""
    cfg = copy.deepcopy(cfg)
    sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sink.bind(("127.0.0.1", 0))
    sink.settimeout(1.0)
    cfg.update(bind_ip="127.0.0.1", rx_port=0, tx_ip="127.0.0.1", tx_port=sink.getsockname()[1])

    emu = IpcEmulator(cfg)
    emu.start()
    results = []
    try:
        # A distinct, exactly representable value per field, of the right type
        sent = emu.rx_spec.tuple(*[bool(i % 2) if f["type"].upper() == "BOOL"
                                   else float(i) + 0.25 if f["type"].upper() in ("REAL", "LREAL")
                                   else i
                                   for i, f in enumerate(emu.rx_spec.fields)])
        src = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        src.sendto(emu.rx_spec.pack(sent), ("127.0.0.1", emu.rx_port))
        src.sendto(b"\x00" * 7, ("127.0.0.1", emu.rx_port))
        time.sleep(0.3)
        s = emu.snapshot
        results.append(("telemetry decoded", s.values == sent))
        results.append(("wrong-size packet rejected", s.rx_bad_size == 1))
        data = sink.recv(65535)
        results.append((f"controller packet is {emu.tx_spec.size} bytes", len(data) == emu.tx_spec.size))
        results.append(("controller packet sent repeatedly", emu.tx_count > 5))
    finally:
        emu.stop()
    for name, ok in results:
        log.info("%s: %s", "PASS" if ok else "FAIL", name)
    return 0 if all(ok for _, ok in results) else 1


# ---------------------------------------------------------------------------------------------------------------------
# GUI (Tkinter, matching the main AC interface)
# ---------------------------------------------------------------------------------------------------------------------

def run_gui(cfg):
    import tkinter as tk
    from tkinter import ttk, font as tkfont

    emu = IpcEmulator(cfg)
    gcfg = cfg["gui"]
    pad = gcfg["spacing"]

    root = tk.Tk()
    root.title(f"IPC Emulator - {emu.description}")
    root.geometry(f"{gcfg['width']}x{gcfg['height']}")
    root.minsize(640, 480)
    root.report_callback_exception = lambda *exc: log.error("GUI error", exc_info=exc)
    try:
        root.iconbitmap("dynisma.ico")
    except tk.TclError:
        pass
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=3)
    root.rowconfigure(2, weight=1)
    mono = tkfont.nametofont("TkFixedFont")

    # Status
    status = ttk.LabelFrame(root, text="Link", padding=pad)
    status.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 0))
    for c in range(4):
        status.columnconfigure(c, weight=1, uniform="status")
    status_vars = {}
    labels = [
        ("rx", f"RX {cfg['bind_ip']}:{cfg['rx_port']} ({emu.rx_spec.size} B)"),
        ("tx", f"TX {cfg['tx_ip']}:{cfg['tx_port']} ({emu.tx_spec.size} B)"),
        ("from", "Source"),
        ("bad", "Wrong size"),
    ]
    for c, (key, title) in enumerate(labels):
        ttk.Label(status, text=title, foreground="gray30").grid(row=0, column=c, sticky="w")
        status_vars[key] = tk.StringVar(value="-")
        ttk.Label(status, textvariable=status_vars[key], font=mono).grid(row=1, column=c, sticky="w")
    error_var = tk.StringVar()
    ttk.Label(status, textvariable=error_var, foreground="red", wraplength=800).grid(
        row=2, column=0, columnspan=4, sticky="w")

    # Values table
    table_frame = ttk.LabelFrame(root, text="Received telemetry (click a row to plot it)", padding=pad)
    table_frame.grid(row=1, column=0, sticky="nsew", padx=pad, pady=pad)
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)
    tree = ttk.Treeview(table_frame, columns=("type", "value"), selectmode="browse")
    tree.heading("#0", text="Field", anchor="w")
    tree.heading("type", text="Type", anchor="w")
    tree.heading("value", text="Value", anchor="e")
    tree.column("#0", width=260, stretch=True)
    tree.column("type", width=80, stretch=False)
    tree.column("value", width=160, stretch=False, anchor="e")
    ttk.Style().configure("Treeview", font=mono, rowheight=mono.metrics("linespace") + 4)
    scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    names = emu.rx_spec.tuple._fields
    for f in emu.rx_spec.fields:
        tree.insert("", "end", iid=f["name"], text=f["name"], values=(f["type"], "-"))

    # Plot of the selected field
    plot_frame = ttk.LabelFrame(root, text="Plot", padding=pad)
    plot_frame.grid(row=2, column=0, sticky="nsew", padx=pad, pady=(0, pad))
    plot_frame.columnconfigure(0, weight=1)
    plot_frame.rowconfigure(0, weight=1)
    canvas = tk.Canvas(plot_frame, background="white", highlightthickness=0, height=150)
    canvas.grid(row=0, column=0, sticky="nsew")

    selected = {"name": None}
    history = deque()  # (t, value) for the selected field

    def on_select(_event):
        sel = tree.selection()
        selected["name"] = sel[0] if sel else None
        history.clear()
        plot_frame.configure(text=f"Plot: {selected['name']}" if selected["name"] else "Plot")

    tree.bind("<<TreeviewSelect>>", on_select)

    def draw_plot():
        canvas.delete("all")
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if len(history) < 2 or w < 50 or h < 30:
            return
        vals = [v for _, v in history]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        t_now = history[-1][0]
        span = gcfg["plot_seconds"]
        margin = 60
        sx = lambda t: margin + (w - margin - pad) * (1 - (t_now - t) / span)
        sy = lambda v: pad + (h - 2 * pad) * (hi - v) / (hi - lo)
        canvas.create_line(margin, pad, margin, h - pad, fill="gray70")
        for v in (lo, hi):
            canvas.create_text(margin - 4, sy(v), text=f"{v:.3g}", anchor="e", font=mono, fill="gray30")
        if lo < 0 < hi:
            canvas.create_line(margin, sy(0), w - pad, sy(0), fill="gray85", dash=(2, 2))
        pts = [c for t, v in history for c in (sx(t), sy(v))]
        canvas.create_line(*pts, fill="#1f77b4", width=1.5)

    # Tiered refresh: values + plot fast, link stats slow
    last_seq = {"seq": -1}
    rx_rate, tx_rate = RateMeter(), RateMeter()

    def fast_update():
        s = emu.snapshot
        if s.seq != last_seq["seq"] and s.values:
            last_seq["seq"] = s.seq
            for name, value in zip(names, s.values):
                text = str(value) if isinstance(value, (bool, int)) else f"{value:12.4f}"
                tree.set(name, "value", text)
            if selected["name"]:
                now = time.monotonic()
                history.append((now, float(getattr(s.values, selected["name"]))))
                while history and now - history[0][0] > gcfg["plot_seconds"]:
                    history.popleft()
        draw_plot()
        root.after(int(1000 / gcfg["fast_update_hz"]), fast_update)

    def slow_update():
        s = emu.snapshot
        status_vars["rx"].set(f"{rx_rate.update(s.rx_count):6.0f} Hz  {s.rx_count} pkts" if s.rx_socket_ok
                              else "not bound")
        status_vars["tx"].set(f"{tx_rate.update(emu.tx_count):6.0f} Hz  {emu.tx_count} pkts")
        status_vars["from"].set(s.rx_from)
        status_vars["bad"].set(f"{s.rx_bad_size}" + (f" (last {s.last_bad_size} B)" if s.rx_bad_size else ""))
        error_var.set(s.error)
        root.after(int(1000 / gcfg["slow_update_hz"]), slow_update)

    def on_close():
        emu.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    emu.start()
    fast_update()
    slow_update()
    root.mainloop()
    return 0


def main():
    parser = argparse.ArgumentParser(description="TwinCAT IPC emulator")
    parser.add_argument("--headless", action="store_true", help="run without a GUI")
    parser.add_argument("--duration", type=float, default=0, help="seconds to run headless (0 = until Ctrl+C)")
    parser.add_argument("--selftest", action="store_true", help="loopback test, then exit")
    parser.add_argument("--config", default=CONFIG_FILE)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a config key")
    args = parser.parse_args()

    cfg = load_config(args.config, args.set)
    setup_logging(cfg)
    try:
        if args.selftest:
            return run_selftest(cfg)
        if args.headless:
            return run_headless(cfg, args.duration)
        return run_gui(cfg)
    except Exception:
        log.exception("Fatal error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
