# Velxio local-run patches (ESP32-S3 + custom chips)

Three things in the published `ghcr.io/davidmonterocrespo24/velxio:master` image
needed fixing to run this project's ESP32-S3 + PCA9685 custom chip simulation
end-to-end. Everything here was verified live on 2026-07-29 — the full Sesame
firmware boots on the emulated S3, drives the OLED, and the PCA9685 chip
generates correct 50Hz servo PWM on all 8 channels during the walk animation
(24,408 edges, 0 errors).

## 1. Missing ESP32-S3 toolchain + ROM (image gap)

The master image only ships the esp32 (LX6) and ESP32-C3 (RISC-V) toolchains
and ROMs. For ESP32-S3 (LX7) you need, inside the container:

```bash
# xtensa-esp32s3-elf toolchain (needed to *compile* for esp32s3):
docker exec velxio sh -c "cd /opt/esp-idf && ./install.sh esp32s3"

# boot ROM (needed to *run* the esp32s3-picsimlab machine):
docker cp simulation/velxio-patches/esp32s3_rev0_rom.bin velxio:/app/lib/
```

(`esp32s3_rev0_rom.bin` comes from the lcgamboa QEMU fork's `pc-bios/`.)

## 2. `wasm_chip_runtime.py` — three custom-chip runtime fixes

`velxio-patches/wasm_chip_runtime.py` replaces `/app/app/services/wasm_chip_runtime.py`:

1. **Timer resync** — `fire_due_timers` advanced overdue repeating timers by a
   single period per call, so any timer that ever fell behind (e.g. during the
   boot stall) stayed permanently overdue and free-ran at scheduler-loop speed.
   Now resyncs to `now + period`.
2. **One-shot re-arm** — `fire_due_timers` unconditionally set `active = False`
   on one-shot timers *after* running the callback, clobbering any re-arm the
   callback itself performed (event-driven chips like our PCA9685 re-arm the
   next edge from inside their timer callback). Now only deactivates if the
   callback didn't re-arm.
3. **Store entry serialization (RLock)** — `_call_indirect` had no thread
   guard, so the QEMU thread (I2C callbacks) and the chip-timer thread could
   enter the same WASM store concurrently, interleaving the shared C stack
   pointer until it blew up ("call stack exhausted" traps under animation
   load). Now every WASM entry goes through a reentrant lock.

## 3. `esp32_worker.py` — chip-timer clock fix

`velxio-patches/esp32_worker.py` replaces `/app/app/services/esp32_worker.py`:
the chip-timer thread computed its "now" from the worker's own epoch while
chip deadlines are expressed in each runtime's sim clock — mixing the two
epochs made the wait overshoot and then fire huge catch-up bursts that
distorted chip PWM. The wait is now computed per-runtime from that runtime's
own `sim_now_nanos()`.

## Applying

```bash
docker cp simulation/velxio-patches/wasm_chip_runtime.py velxio:/app/app/services/
docker cp simulation/velxio-patches/esp32_worker.py       velxio:/app/app/services/
docker restart velxio
```

Both files are deltas against `ghcr.io/davidmonterocrespo24/velxio:master` as
of 2026-07-29 and are good candidates to upstream to
[davidmonterocrespo24/velxio](https://github.com/davidmonterocrespo24/velxio).

## Verifying with the headless test

`../velxio_headless_test.py` (in the folder above this one) compiles the sim
firmware via the backend API, starts an ESP32-S3 worker with the SSD1306 and
the PCA9685 chip attached over the simulation websocket, then drives the walk
animation from the serial CLI and watches for boot completion, chip ready,
I2C ACKs, and (with the debug chip build) per-channel PWM edge timing.
