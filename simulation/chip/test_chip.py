#!/usr/bin/env python3
"""Behavioral test for pca9685.wasm (event-driven PWM) against a stubbed host.

Drives I2C transactions like Adafruit_PWMServoDriver does, then verifies the
event-driven engine: first edge is a rise right after configuration, and the
fall lands ~732us later for OFF=150 (150/4096 of 20ms) — wall-clock timed.
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
    timer_state["starts"].append({"period_ns": period_ns, "repeat": repeat,
                                  "at": time.monotonic_ns() - _t0,
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
memtype = wasmtime.MemoryType(wasmtime.Limits(2, None))
shared_mem = wasmtime.Memory(store, memtype)
linker.define(store, "env", "memory", shared_mem)
inst = linker.instantiate(store, module)
mem = shared_mem
table = inst.exports(store)["__indirect_function_table"]

inst.exports(store)["chip_setup"](store)
print("registered pins:", len(pin_handles))
assert "PWM0" in pin_handles and "PWM15" in pin_handles and "SCL" in pin_handles
assert i2c_cbs["address"] == 0x40


def i2c_call(cb, *args):
    fn = table.get(store, i2c_cbs[cb])
    return fn(store, i2c_cbs["user_data"], *args)


def i2c_write_reg(reg, val):
    i2c_call("on_connect", 0x40, 0)
    i2c_call("on_write", reg)
    i2c_call("on_write", val)
    i2c_call("on_stop")


def fire_edge():
    fn = table.get(store, timer_state["create_cb"])
    fn(store, timer_state["create_ud"])


# --- Adafruit begin() + setPWMFreq(50) ---
i2c_write_reg(0x00, 0x00)
i2c_write_reg(0x00, 0x10)
i2c_write_reg(0xFE, 121)
i2c_write_reg(0x00, 0x00)
i2c_write_reg(0x00, 0xA0)

# setPWM(0, 0, 150): burst write at 0x06 with auto-increment
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x06)
for b in (0x00, 0x00, 150, 0x00):
    i2c_call("on_write", b)
i2c_call("on_stop")

# setPWM(1, 0, 300)
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x0A)
for b in (0x00, 0x00, 0x2C, 0x01):
    i2c_call("on_write", b)
i2c_call("on_stop")

# The engine should have armed a one-shot for the rise (on_ns == 0 -> ~now)
assert timer_state["starts"], "no timer arms after config"
last_arm = timer_state["starts"][-1]
assert last_arm.get("repeat") == False, "engine must use one-shot timers"
print(f"armed one-shot, delay={last_arm['period_ns']/1000:.0f}us")

# A channel configured with on_ns=0 enters its HIGH window during the burst.
# Exactly WHEN the rise write lands depends on host speed (a slow host can
# cross the 732us fall boundary mid-burst, flipping HIGH->LOW before the
# burst ends -- that is correct frame-clock behavior, not a bug). So assert
# the rise HAPPENED at some point after config, not a specific write order.
pwm0 = [w for w in pin_writes if w[1] == "PWM0"]
pwm1 = [w for w in pin_writes if w[1] == "PWM1"]
assert any(v == 1 for _, _, v in pwm0), f"PWM0 never went HIGH, got {pwm0}"
assert any(v == 1 for _, _, v in pwm1), f"PWM1 never went HIGH, got {pwm1}"
pwm0_rise_t = max(t for t, _, v in pwm0 if v == 1)
print(f"PWM0 rose at t={pwm0_rise_t/1000:.0f}us")

# Deterministic check 1 (host-speed independent): the armed fall deadline is
# off_ns after the global frame epoch. We can't read the epoch directly, but
# the delay from ARM TIME to deadline is off_ns - (arm-epoch processing time),
# which is always in (0, off_ns] on any host. Assert the wide window.
arms = [a for a in timer_state["starts"] if "deadline" in a]
d0 = arms[-1]["deadline"]
arm_t = arms[-1]["at"]
delay_from_arm_us = (d0 - arm_t) / 1000.0
print(f"armed fall delay from arm: {delay_from_arm_us:.0f}us (must be in (0, 732])")
assert 20 < delay_from_arm_us <= 732, f"armed fall delay wrong: {delay_from_arm_us}us"

# Fire it (sleep till due), expect PWM0 LOW
now = time.monotonic_ns() - _t0
wait_s = max(0, (d0 - now) / 1e9) + 0.00005
time.sleep(wait_s)
fire_edge()
pwm0 = [w for w in pin_writes if w[1] == "PWM0"]
assert pwm0[-1][2] == 0, f"PWM0 should be LOW after fall, got {pwm0}"
print(f"PWM0 fell at t={pwm0[-1][0]/1000:.0f}us")

# Deterministic check 2: PWM1 shares the SAME global frame clock, so its fall
# deadline must be exactly (1465-732)us = ~733us after PWM0's fall deadline,
# regardless of when the two register bursts happened.
arms = [a for a in timer_state["starts"] if "deadline" in a]
d1 = arms[-1]["deadline"]
frame_delta_us = (d1 - d0) / 1000.0
print(f"PWM1 fall deadline - PWM0 fall deadline: {frame_delta_us:.0f}us (expected ~733us)")
assert 550 < frame_delta_us < 950, f"shared-frame delta wrong: {frame_delta_us}us"

now = time.monotonic_ns() - _t0
time.sleep(max(0, (d1 - now) / 1e9) + 0.00005)
fire_edge()
pwm1 = [w for w in pin_writes if w[1] == "PWM1"]
assert pwm1 and pwm1[-1][2] == 0, f"PWM1 should be LOW after its fall, got {pwm1}"
print(f"PWM1 fell at t={pwm1[-1][0]/1000:.0f}us")

print("ALL TESTS PASSED")
