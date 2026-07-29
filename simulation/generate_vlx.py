#!/usr/bin/env python3
"""Generates simulation/sesame-pca9685.vlx — a complete Velxio workspace for
the Sesame PCA9685 build: ESP32-S3 + PCA9685 custom chip + 8 servos +
4-pin I2C OLED + 5V supply, with the sim firmware variant embedded.

Re-run this after editing firmware-sim/ or the chip to regenerate the file:
    python3 simulation/generate_vlx.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
# Vendored copy of levkropp/pca9685-velxio lives in-repo so CI and fresh
# clones can regenerate without a sibling checkout. Override with CHIP_DIR.
CHIP_REPO = os.environ.get("CHIP_DIR", os.path.join(HERE, "chip"))


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# --- source files -----------------------------------------------------------
fw_dir = os.path.join(HERE, "firmware-sim")
firmware_files = [
    {"name": "sesame-firmware-sim.ino", "content": read(os.path.join(fw_dir, "sesame-firmware-sim.ino"))},
    {"name": "face-bitmaps.h",          "content": read(os.path.join(fw_dir, "face-bitmaps.h"))},
    {"name": "movement-sequences.h",    "content": read(os.path.join(fw_dir, "movement-sequences.h"))},
    {"name": "captive-portal.h",        "content": read(os.path.join(fw_dir, "captive-portal.h"))},
]

chip_c = read(os.path.join(CHIP_REPO, "pca9685.c"))
chip_json_text = read(os.path.join(CHIP_REPO, "pca9685.chip.json"))
import base64
chip_wasm_b64 = base64.b64encode(
    open(os.path.join(CHIP_REPO, "dist", "pca9685.wasm"), "rb").read()
).decode("ascii")

# --- board ------------------------------------------------------------------
boards = [
    {
        "id": "esp32-s3",
        "boardKind": "esp32-s3",
        "x": 60,
        "y": 120,
        "activeFileGroupId": "group-esp32-s3",
        "languageMode": "arduino",
        "serialBaudRate": 115200,
        "libraries": [
            "Adafruit SSD1306",
            "Adafruit GFX Library",
            "Adafruit PWM Servo Driver Library",
        ],
    }
]

# --- components -------------------------------------------------------------
def servo(i, x, y):
    return {
        "id": f"sv{i}",
        "metadataId": "servo",
        "x": x,
        "y": y,
        "properties": {"angle": "0", "horn": "single", "hornColor": "#ccc"},
    }

components = [
    {
        "id": "oled",
        "metadataId": "ssd1306-i2c-4pin",
        "x": 80,
        "y": 470,
        "properties": {"i2cAddress": "0x3c"},
    },
    {
        "id": "pca9685",
        "metadataId": "custom-chip",
        "x": 430,
        "y": 170,
        "properties": {
            "chipName": "PCA9685 16-Ch PWM Driver",
            "sourceC": chip_c,
            "chipJson": chip_json_text,
            "wasmBase64": chip_wasm_b64,
            "attrs": {},
        },
    },
    {
        "id": "psu",
        "metadataId": "power-supply",
        "x": 430,
        "y": 520,
        "properties": {"mode": "dc", "voltage": 5, "currentLimit": 3, "frequency": 50},
    },
] + [servo(i, 690 + (i % 4) * 110, 110 if i < 4 else 330) for i in range(8)]

# --- wires ------------------------------------------------------------------
RED, BLK, GOLD, PURP = "#ff4444", "#000000", "#c9a227", "#a855f7"
wires = []


def wire(start_id, start_pin, end_id, end_pin, color, signal):
    wires.append({
        "id": f"w{len(wires)}",
        "start": {"componentId": start_id, "pinName": start_pin},
        "end":   {"componentId": end_id,   "pinName": end_pin},
        "color": color,
        "signalType": signal,
    })


# I2C bus (shared between PCA9685 and OLED, exactly like the real build)
wire("esp32-s3", "8", "pca9685", "SDA", GOLD, "i2c")
wire("esp32-s3", "9", "pca9685", "SCL", GOLD, "i2c")
wire("esp32-s3", "8", "oled", "SDA", GOLD, "i2c")
wire("esp32-s3", "9", "oled", "SCL", GOLD, "i2c")

# Logic power
wire("esp32-s3", "3V3", "pca9685", "VCC", RED, "power-vcc")
wire("esp32-s3", "GND", "pca9685", "GND", BLK, "power-gnd")
wire("esp32-s3", "3V3", "oled", "VCC", RED, "power-vcc")
wire("esp32-s3", "GND", "oled", "GND", BLK, "power-gnd")

# Servo PWM channels 0-7
for i in range(8):
    wire("pca9685", f"PWM{i}", f"sv{i}", "PWM", PURP, "pwm")

# Servo rail: the PSU feeds the PCA9685's screw terminal; servos draw power
# THROUGH the board's rail pins — exactly like plugging a real servo's 3-pin
# connector into the module (servos never touch the PSU directly).
wire("psu", "SIG", "pca9685", "V+", RED, "power-vcc")
wire("psu", "GND", "pca9685", "GND", BLK, "power-gnd")
for i in range(8):
    wire("pca9685", "V+", f"sv{i}", "V+", RED, "power-vcc")
    wire("pca9685", "GND", f"sv{i}", "GND", BLK, "power-gnd")

# --- file groups ------------------------------------------------------------
file_groups = {
    "group-esp32-s3": firmware_files,
    "group-chip-pca9685": [
        {"name": "pca9685.c", "content": chip_c},
        {"name": "pca9685.chip.json", "content": chip_json_text},
    ],
}

payload = {
    "format": "velxio-project",
    "version": 1,
    "name": "Sesame Robot — PCA9685 Edition (Velxio Sim)",
    "boards": boards,
    "fileGroups": file_groups,
    "components": components,
    "wires": wires,
    "activeBoardId": "esp32-s3",
}

out = os.path.join(HERE, "sesame-pca9685.vlx")
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=1)

print(f"wrote {out}")
print(f"  boards: {len(boards)}, components: {len(components)}, wires: {len(wires)}")
print(f"  file groups: {list(file_groups)} ({sum(len(v) for v in file_groups.values())} files)")
