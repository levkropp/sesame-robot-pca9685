# Velxio Simulation — Run Sesame Before You Build It

This folder contains a complete [Velxio](https://github.com/davidmonterocrespo24/velxio)
workspace for the PCA9685 build: **ESP32-S3 + PCA9685 driver chip + 8 servos + the
4-pin I2C OLED + a 5V servo rail**, running a sim variant of this fork's real firmware.

Open it, press compile/run, and you can watch the robot's face animate on a virtual
OLED and drive walk/wave/dance animations from the Serial Monitor — all before
soldering or wiring anything physical.

| File | What it is |
|---|---|
| `sesame-pca9685.vlx` | The complete Velxio project (open this) |
| `firmware-sim/` | Sim variant of the firmware (`VELXIO_SIM` guards stub out only the WiFi/web/DNS/mDNS code — everything else is byte-identical to the real firmware) |
| `generate_vlx.py` | Regenerates the `.vlx` after you edit firmware or the chip |

The PCA9685 driver itself is a [custom Velxio chip](https://github.com/levkropp/pca9685-velxio)
(behaviorally verified against the Adafruit library's I2C transaction sequence).

## Quick start

1. Open **[velxio.dev](https://velxio.dev)** (no install), or self-host:
   `docker run -d -p 3080:80 ghcr.io/davidmonterocrespo24/velxio:master` → http://localhost:3080
2. Click **Open `.vlx`** and select `sesame-pca9685.vlx`.
3. Click the board, then **Compile**. First compile downloads the ESP32-S3 toolchain
   and can take a few minutes; the Adafruit libraries needed (SSD1306, GFX,
   PWM Servo Driver) are already declared on the board and resolve from Velxio's
   Library Manager.
4. Press **Run**.

> [!NOTE]
> **Self-hosting on the `master` image?** Running the ESP32-S3 + custom-chip
> path locally currently needs the toolchain/ROM files and three runtime fixes
> in [`velxio-patches/`](velxio-patches/) (all verified live: the full firmware
> boots, OLED renders, and the PCA9685 chip emits correct 50 Hz PWM on all 8
> channels during walk animations — 24k edges, 0 errors). velxio.dev may or may
> not have these yet; the patches folder has details and is upstream-PR material.

## What you should see on first run

- Serial Monitor: boot messages, ending with
  `VELXIO_SIM: WiFi/web/DNS/mDNS stubbed out; use the Serial CLI.` then
  `Sesame boot complete.`
- The OLED shows the **rest face**, then the idle animation with periodic blinks.
- After ~30s without input, a "VELXIO SIM | drive me from Serial Monitor"
  banner scrolls across the top of the OLED.
- The chip console shows `PCA9685 ready (I2C 0x40, 16ch PWM @ 50Hz frame)`.

## Drive it from the Serial Monitor

Type commands into the Serial Monitor input and hit enter:

| Command | Effect |
|---|---|
| `rn wf` | walk forward |
| `rn wb` | walk backward |
| `rn tl` / `rn tr` | turn left / right |
| `rn wv` | wave |
| `rn dn` | dance |
| `rn rs` | rest pose |
| `rn st` | stand |
| `rn pt`, `rn pu`, `rn bw`, `rn ct`, `rn fk`, `rn wm`, `rn sk`, `rn sg`, `rn dd`, `rn cb`, `rn sw` | point, pushup, bow, cute, freaky, worm, shake, shrug, dead, crab, swim |
| `all 90` | all 8 servos to 90° |
| `<motor> <angle>` (e.g. `3 120`) | single servo to angle |
| `st` | print subtrim values |
| `st 2 -5` | set subtrim on motor 2 |

Watch the 8 virtual servos sweep as animations play — that's the same PCA9685
I2C traffic your real board will generate.

## Virtual → physical wiring map

The canvas wiring is 1:1 with the real Phase-1 (tethered) build:

| Virtual wire | Physical connection |
|---|---|
| board `8` → chip `SDA`, board `9` → chip `SCL` | S3 Mini GPIO8→PCA9685 SDA, GPIO9→SCL |
| board `8`/`9` → OLED `SDA`/`SCL` | same I2C bus tapped at the OLED |
| board `3V3`/`GND` → chip `VCC`/`GND` + OLED `VCC`/`GND` | logic power from S3 Mini |
| chip `PWMn` → servo `n` `PWM` | PCA9685 channel n → servo n (motor n+1) |
| PSU `SIG` → all servo `V+` + chip `V+` | 5V/3A rail (USB-C breakout in Phase 1, buck output in Phase 2) |
| PSU `GND` → all servo `GND` + board `GND` | common ground |

## Notes & troubleshooting

- **Networking is intentionally stubbed** (`#define VELXIO_SIM` in
  `firmware-sim/sesame-firmware-sim.ino`). The emulator can't emulate a soft-AP,
  so the web UI / JSON API / captive portal are compiled out in the sim build.
  Everything else — faces, animations, PCA9685, subtrim, Serial CLI — is the
  real firmware.
- **ESP32 core**: Velxio's Xtensa emulation requires arduino-esp32 **2.0.17**
  (it manages this itself; don't override the core version).
- **If the OLED stays black or the chip doesn't respond to I2C**: the QEMU S3
  backend may be picky about which pins route I2C. Try remapping the two defines
  near the top of `sesame-firmware-sim.ino` (`I2C_SDA`/`I2C_SCL`) to another free
  pair **in the sim only** (the virtual DevKit board has no RGB LED on GPIO21,
  so even pins that are reserved on the real S3-Zero-M are safe to test with in
  the emulator). Real hardware must stay on GPIO8/9.
- **After editing firmware or the chip**, regenerate the project file:
  `python3 simulation/generate_vlx.py` (it re-embeds `firmware-sim/` and the
  chip sources + WASM from `~/Documents/pca9685-velxio-chip`).
