#!/usr/bin/env python3
"""Behavioral test for pca9685.wasm (event-driven PWM) against a stubbed host.

Drives I2C transactions like Adafruit_PWMServoDriver does, then verifies the
event-driven engine with host-speed-independent checks:

  1. I2C register model (auto-increment write/read-back)
  2. Phase-synced rise when a channel is configured with on=0
  3. The 50 Hz frame repeats: two consecutive rises are ~20000us apart

Timing-sensitive measurements (wall-clock pulse widths, exact per-edge
delays) are intentionally avoided — they depend on host speed. The frame
period check anchors both rises to the global frame epoch, so it is exact.
"""
import sys
import time

import wasmtime

WASM = sys.argv[1] if len(sys.argv) > 1 else "dist/pca9685.wasm"

store = wasmtime.Store()
linker = wasmtime.Linker(store.engine)

pin_handles = {}
handle_names = {}
pin_writes = []          # (monotonic_ns, pin_name, value)
i2c_cbs = {}
timer_state = {"create_cb": None, "create_ud": None, "starts": []}
next_handle = [1]
_t0 = time.monotonic_ns()


def read_cstr(ptr):
    data = mem.read(store, ptr, ptr + 4096)
    nul = data.index(0) if 0 in data else len(data)
    return bytes(data[:nul]).decode()


def vx_pin_register(name_ptr, mode):
    h = next_handle[0]
    next_handle[0] += 1
    name = read_cstr(name_ptr)
    handle_names[h] = name
    pin_handles[name] = h
    return h


def vx_pin_write(handle, value):
    pin_writes.append((time.monotonic_ns() - _t0, handle_names.get(handle, f"?{handle}"), value))


def vx_pin_read(handle):
    return 0


def vx_i2c_attach(cfg_ptr):
    import struct as st
    raw = mem.read(store, cfg_ptr, cfg_ptr + 64)
    addr = raw[0]
    on_connect, on_read, on_write, on_stop = st.unpack_from("<iiii", raw, 12)
    ud = st.unpack_from("<i", raw, 28)[0]
    i2c_cbs.update(address=addr, on_connect=on_connect, on_read=on_read,
                   on_write=on_write, on_stop=on_stop, user_data=ud)
    return 1


def vx_timer_create(cb, ud):
    timer_state["create_cb"] = cb
    timer_state["create_ud"] = ud
    return 0


def vx_timer_start(handle, period_ns, repeat):
    timer_state["starts"].append({"at": time.monotonic_ns() - _t0,
                                  "deadline": time.monotonic_ns() - _t0 + period_ns})


def vx_timer_stop(handle):
    timer_state["starts"].append({"stop": True})


def vx_sim_now_nanos():
    return time.monotonic_ns() - _t0


def vx_log(msg_ptr):
    print("[chip]", read_cstr(msg_ptr))


for name, fn, ty in [
    ("vx_pin_register", vx_pin_register, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_pin_read", vx_pin_read, wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_pin_write", vx_pin_write, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [])),
    ("vx_i2c_attach", vx_i2c_attach, wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_timer_create", vx_timer_create, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_timer_start", vx_timer_start, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i64(), wasmtime.ValType.i32()], [])),
    ("vx_timer_stop", vx_timer_stop, wasmtime.FuncType([wasmtime.ValType.i32()], [])),
    ("vx_sim_now_nanos", vx_sim_now_nanos, wasmtime.FuncType([], [wasmtime.ValType.i64()])),
    ("vx_log", vx_log, wasmtime.FuncType([wasmtime.ValType.i32()], [])),
]:
    linker.define(store, "env", name, wasmtime.Func(store, ty, fn))

module = wasmtime.Module.from_file(store.engine, WASM)
shared_mem = wasmtime.Memory(store, wasmtime.MemoryType(wasmtime.Limits(2, None)))
linker.define(store, "env", "memory", shared_mem)
inst = linker.instantiate(store, module)
mem = shared_mem
table = inst.exports(store)["__indirect_function_table"]

inst.exports(store)["chip_setup"](store)
print("registered pins:", len(pin_handles))
assert "PWM0" in pin_handles and "PWM15" in pin_handles and "SCL" in pin_handles
assert i2c_cbs["address"] == 0x40, f"bad i2c addr {i2c_cbs['address']}"


def i2c_call(cb, *args):
    fn = table.get(store, i2c_cbs[cb])
    return fn(store, i2c_cbs["user_data"], *args)


def i2c_write_reg(reg, val):
    i2c_call("on_connect", 0x40, 0)
    i2c_call("on_write", reg)
    i2c_call("on_write", val)
    i2c_call("on_stop")


def i2c_read_reg(reg):
    i2c_call("on_connect", 0x40, 0)
    i2c_call("on_write", reg)
    i2c_call("on_connect", 0x40, 1)
    v = i2c_call("on_read")
    i2c_call("on_stop")
    return v


def fire_edge():
    fn = table.get(store, timer_state["create_cb"])
    fn(store, timer_state["create_ud"])


def fire_until(cond, timeout_s=30.0):
    """Fire edges at their deadlines until cond() is true."""
    t_end = time.time() + timeout_s
    while time.time() < t_end:
        if cond():
            return True
        arms = [a for a in timer_state["starts"] if "deadline" in a]
        if not arms:
            time.sleep(0.0002)
            continue
        d = arms[-1]["deadline"]
        now = time.monotonic_ns() - _t0
        time.sleep(max(0, (d - now) / 1e9) + 0.00005)
        fire_edge()
    return False


# --- Adafruit begin() + setPWMFreq(50) ---
i2c_write_reg(0x00, 0x00)
i2c_write_reg(0x00, 0x10)
i2c_write_reg(0xFE, 121)
i2c_write_reg(0x00, 0x00)
i2c_write_reg(0x00, 0xA0)

# --- I2C register model: MODE1 read-back ---
assert i2c_read_reg(0x00) == 0xA0, "MODE1 read-back wrong"
print("I2C register model OK (MODE1=0xA0)")

# --- setPWM(0, 0, 150): burst-write 4 regs at 0x06 (auto-increment) ---
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x06)
for b in (0x00, 0x00, 150, 0x00):
    i2c_call("on_write", b)
i2c_call("on_stop")

# Read back OFF_L (0x08) with auto-increment: write pointer 0x08, read
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x08)
i2c_call("on_connect", 0x40, 1)
off_l = i2c_call("on_read")
off_h = i2c_call("on_read")   # AI advances pointer
i2c_call("on_stop")
assert off_l == 150 and off_h == 0, f"OFF read-back wrong: {off_l} {off_h}"
print("I2C register model OK (OFF_L=150 read-back)")

# --- Phase-synced rise: channel configured with on=0 goes HIGH ---
assert fire_until(lambda: any(w[1] == "PWM0" and w[2] == 1 for w in pin_writes)), "PWM0 never went HIGH"
pwm0_rise_t = max(t for t, _, v in [w for w in pin_writes if w[1] == "PWM0"] if v == 1)
print(f"PWM0 rose at t={pwm0_rise_t/1000:.0f}us")

# --- The 50 Hz frame repeats: fall, then rise again one frame later ---
pwm0 = lambda: [w for w in pin_writes if w[1] == "PWM0"]
assert fire_until(lambda: pwm0() and pwm0()[-1][2] == 0), "PWM0 never fell"
print(f"PWM0 fell at t={pwm0()[-1][0]/1000:.0f}us")

assert fire_until(lambda: pwm0() and pwm0()[-1][2] == 1), "PWM0 never rose again"
rise2_t = pwm0()[-1][0]
frame_us = (rise2_t - pwm0_rise_t) / 1000.0
print(f"frame period (rise to rise): {frame_us:.0f}us (expected ~20000us)")
assert 18000 < frame_us < 22000, f"frame period wrong: {frame_us}us"

print("ALL TESTS PASSED")
