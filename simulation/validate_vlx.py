#!/usr/bin/env python3
"""Validates simulation/sesame-pca9685.vlx.

Mirrors the checks velxio's parseVlxFile() enforces, plus deeper project-specific
invariants (file-group naming conventions, chip sources matching the vendored
copy in simulation/chip/, wire endpoints resolving to real pins, valid WASM).

Run:  python3 simulation/validate_vlx.py
CI:   same, exits non-zero on any failure.
"""
import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VLX = os.path.join(HERE, "sesame-pca9685.vlx")
CHIP_DIR = os.path.join(HERE, "chip")

failures = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        failures.append(msg)
        print(f"FAIL: {msg}")


p = json.load(open(VLX))

# --- mirror validatePayload() from velxio's vlxFile.ts ---
check(isinstance(p, dict), "payload is a JSON object")
check(p.get("format") == "velxio-project", 'format == "velxio-project"')
check(isinstance(p.get("version"), (int, float)) and p["version"] <= 1, "version <= 1")
for field in ("boards", "components", "wires"):
    check(isinstance(p.get(field), list), f'"{field}" is an array')
check(isinstance(p.get("fileGroups"), dict), '"fileGroups" is an object')

# --- board / group conventions (loadProjectState + addBoard naming) ---
b = p["boards"][0]
check(b.get("boardKind") == "esp32-s3", "board kind is esp32-s3")
check("group-esp32-s3" in p["fileGroups"], "board file group named group-esp32-s3")

# --- components well-formed ---
for c in p["components"]:
    for k in ("id", "metadataId", "x", "y", "properties"):
        check(k in c, f"component {c.get('id', '?')} has field '{k}'")

chip = next((c for c in p["components"] if c["metadataId"] == "custom-chip"), None)
check(chip is not None, "a custom-chip component exists")
chip_json = json.loads(chip["properties"]["chipJson"])
chip_pins = {x for x in chip_json["pins"] if x}
check(len(chip["properties"]["wasmBase64"]) > 100, "custom chip has wasmBase64")

wasm = base64.b64decode(chip["properties"]["wasmBase64"])
check(wasm[:4] == b"\0asm", "embedded wasm has valid magic header")

# --- wire endpoints resolve to real components and real pins ---
comp_ids = {c["id"] for c in p["components"]} | {"esp32-s3"}
board_pins = {"8", "9", "3V3", "GND"}
oled_pins = {"GND", "VCC", "SCL", "SDA"}
servo_pins = {"PWM", "V+", "GND"}
psu_pins = {"SIG", "GND", "+", "−", "-", "VCC"}


def pin_ok(cid, pin):
    if cid == "esp32-s3":
        return pin in board_pins
    if cid == "oled":
        return pin in oled_pins
    if cid == "pca9685":
        return pin in chip_pins
    if cid.startswith("sv"):
        return pin in servo_pins
    if cid == "psu":
        return pin in psu_pins
    return False


for w in p["wires"]:
    for end in ("start", "end"):
        e = w[end]
        check(e["componentId"] in comp_ids, f"{w['id']}: {e['componentId']} exists")
        check(pin_ok(e["componentId"], e["pinName"]),
              f"{w['id']}: pin '{e['pinName']}' valid on {e['componentId']}")

# --- firmware group ---
fg = {f["name"]: f["content"] for f in p["fileGroups"]["group-esp32-s3"]}
for name in ("sesame-firmware-sim.ino", "face-bitmaps.h",
             "movement-sequences.h", "captive-portal.h"):
    check(name in fg and len(fg.get(name, "")) > 100, f"firmware file '{name}' embedded")
check("#define VELXIO_SIM" in fg.get("sesame-firmware-sim.ino", ""),
      "firmware has VELXIO_SIM define")

# --- chip group matches the vendored sources in simulation/chip/ ---
cg = {f["name"]: f["content"] for f in p["fileGroups"]["group-chip-pca9685"]}
check(cg.get("pca9685.c") == open(os.path.join(CHIP_DIR, "pca9685.c")).read(),
      "pca9685.c matches vendored chip source")
check(cg.get("pca9685.chip.json") == open(os.path.join(CHIP_DIR, "pca9685.chip.json")).read(),
      "pca9685.chip.json matches vendored chip metadata")
check(wasm == open(os.path.join(CHIP_DIR, "dist", "pca9685.wasm"), "rb").read(),
      "embedded wasm matches vendored dist/pca9685.wasm")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL VALIDATION PASSED")
