#!/usr/bin/env python3
"""Headless end-to-end test: run the sesame sim firmware on velxio's emulated
ESP32-S3 with the SSD1306 OLED + PCA9685 custom chip attached, then drive the
walk animation over the serial CLI and verify PWM edges come out of the chip.

Usage: python3 /tmp/opencode/velxio_headless_test.py
"""
import asyncio
import base64
import json
import sys
import time

import websockets

WS_URL = "ws://localhost:3080/api/simulation/ws/headless-test::esp32-s3"
COMPILE_RESULT = "/tmp/opencode/compile_result3.json"
WASM_B64 = open("/home/min/Documents/pca9685-velxio-chip/dist/pca9685.wasm.base64.txt").read().strip()

firmware_b64 = json.load(open(COMPILE_RESULT))["result"]["binary_content"]

sensors = [
    {"sensor_type": "ssd1306", "pin": 200 + 0x3C, "addr": 0x3C},
    {
        "sensor_type": "custom-chip",
        "pin": 0xFF,
        "wasm_b64": WASM_B64,
        "attrs": {},
        "pin_map": {
            "SCL": 9, "SDA": 8,
            # PWM outputs mapped to unused GPIOs so edges are observable
            # as gpio_change events on the websocket.
            **{f"PWM{i}": 10 + i for i in range(8)},
        },
    },
]

serial_buf = ""
boot_done = asyncio.Event()
chip_ready = asyncio.Event()
walk_detected = asyncio.Event()
pwm_edges = []
i2c_to_40 = []


async def main():
    global serial_buf
    print(f"firmware: {len(firmware_b64) * 3 // 4 // 1024} KB bin")
    async with websockets.connect(WS_URL, max_size=50 * 1024 * 1024) as ws:
        await ws.send(json.dumps({
            "type": "start_esp32",
            "data": {
                "board": "esp32-s3",
                "firmware_b64": firmware_b64,
                "sensors": sensors,
                "wifi_enabled": False,
            },
        }))
        print("start_esp32 sent; listening...")

        async def send_cli(cmd: str):
            payload = {"type": "esp32_serial_input",
                       "data": {"bytes": list(cmd.encode()), "uart": 0}}
            await ws.send(json.dumps(payload))

        deadline = time.time() + 180
        sent_walk = False
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue
            msg = json.loads(raw)
            t = msg.get("type")
            data = msg.get("data", {}) if isinstance(msg.get("data"), dict) else {}

            if t == "serial_output":
                text = data.get("data", "")
                uart = data.get("uart", 0)
                if uart == 0 and text:
                    serial_buf += text
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    if "Sesame boot complete." in serial_buf and not boot_done.is_set():
                        boot_done.set()
                        print("\n>>> BOOT COMPLETE — OLED (0x3c) and PCA9685 (0x40) both responded")
                    if ("walk" in serial_buf.lower() or "forward" in serial_buf.lower()) and sent_walk:
                        walk_detected.set()
            elif t == "chip_log":
                text = data.get("text", "")
                print(f"[chip] {text}")
                if "PCA9685 ready" in text:
                    chip_ready.set()
            elif t == "chip_error" or t == "chip_warning":
                print(f"[chip:{t}] {data}")
            elif t == "gpio_change":
                pin, state = data.get("pin"), data.get("state")
                if pin is not None and 10 <= pin <= 17:
                    pwm_edges.append((time.time(), pin, state))
            elif t in ("i2c_event", "i2c_trace"):
                addr = data.get("addr")
                if addr in (0x40, 64):
                    i2c_to_40.append((t, data))
            elif t == "error":
                print(f"[error] {msg}")
            elif t == "system":
                ev = data.get("event")
                if ev in ("crash", "reboot"):
                    print(f"[system] {ev}: {data}")

            if boot_done.is_set() and not sent_walk:
                sent_walk = True
                print("\n>>> sending serial CLI: 'rn wf\\n' (walk forward)")
                await send_cli("rn wf\n")

            if sent_walk and len(pwm_edges) > 20:
                break

        print("\n\n================ RESULTS ================")
        print(f"boot_done:     {boot_done.is_set()}")
        print(f"chip_ready:    {chip_ready.is_set()}  (PCA9685 WASM loaded + ready log)")
        print(f"i2c to 0x40:   {len(i2c_to_40)} event(s)")
        for ev in i2c_to_40[:5]:
            print(f"   {ev}")
        print(f"pwm_edges:     {len(pwm_edges)} on GPIO10-17")
        if pwm_edges:
            from collections import Counter
            c = Counter(pin for _, pin, _ in pwm_edges)
            print(f"   edges per channel: {dict(sorted(c.items()))}")
            t0 = pwm_edges[0][0]
            recent = [e for e in pwm_edges if e[0] - t0 < 0.2]
            print(f"   first 0.2s: {len(recent)} edges (expect ~2/channel @50Hz)")
        print("=========================================")
        ok = boot_done.is_set() and chip_ready.is_set() and len(pwm_edges) > 0
        print("VERDICT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1


sys.exit(asyncio.run(main()))
