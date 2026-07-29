#!/usr/bin/env python3
"""Behavioral smoke test for pca9685.wasm against a stubbed velxio host.

Simulates the velxio chip runtime: stubs vx_* host functions, calls
chip_setup(), then drives I2C transactions like Adafruit_PWMServoDriver
does, fires the frame timer, and asserts PWM0 produces the expected
HIGH window (~14 of 400 ticks for OFF=150 counts at 50Hz).
"""
import wasmtime

import sys
WASM = sys.argv[1] if len(sys.argv) > 1 else "dist/pca9685.wasm"

store = wasmtime.Store()
linker = wasmtime.Linker(store.engine)

pin_handles = {}
pin_writes = []          # (pin_name, value)
i2c_cbs = {}             # callback name -> table index
timer_cb_index = [None, 0]
next_handle = [1]
handle_names = {}

def vx_pin_register(name_ptr, mode):
    h = next_handle[0]; next_handle[0] += 1
    name = read_cstr(name_ptr)
    handle_names[h] = name
    pin_handles[name] = h
    return h

mem_holder = {}

def read_cstr(ptr):
    mem = mem_holder["mem"]
    data = mem.read(store, ptr, ptr + 4096)
    nul = data.index(0) if 0 in data else len(data)
    return bytes(data[:nul]).decode()

def vx_pin_write(handle, value):
    pin_writes.append((handle_names.get(handle, f"?{handle}"), value))

def vx_pin_read(handle):
    return 0

def vx_i2c_attach(cfg_ptr):
    mem = mem_holder["mem"]
    raw = mem.read(store, cfg_ptr, cfg_ptr + 64)
    import struct
    addr = raw[0]
    idx = 8  # skip address(1)+pad(3)+scl(4)
    scl, sda = struct.unpack_from("<ii", raw, 4)
    on_connect, on_read, on_write, on_stop = struct.unpack_from("<iiii", raw, 12)
    ud = struct.unpack_from("<i", raw, 28)[0]
    i2c_cbs.update(address=addr, on_connect=on_connect, on_read=on_read,
                   on_write=on_write, on_stop=on_stop, user_data=ud)
    return 1

def vx_timer_create(cb_index, ud):
    timer_cb_index[0] = cb_index
    timer_cb_index[1] = ud
    return 1

def vx_timer_start(t, period_ns, repeat):
    pass

def vx_timer_stop(t):
    pass

def vx_log(msg_ptr):
    print("[chip]", read_cstr(msg_ptr))

env = wasmtime.Module(store.engine, """
(module
  (import "env" "vx_pin_register" (func $vx_pin_register (param i32) (result i32)))
  (import "env" "vx_pin_read" (func $vx_pin_read (param i32) (result i32)))
  (import "env" "vx_pin_write" (func $vx_pin_write (param i32 i32)))
  (import "env" "vx_i2c_attach" (func $vx_i2c_attach (param i32) (result i32)))
  (import "env" "vx_timer_create" (func $vx_timer_create (param i32 i32) (result i32)))
  (import "env" "vx_timer_start" (func $vx_timer_start (param i32 i64 i32)))
  (import "env" "vx_timer_stop" (func $vx_timer_stop (param i32)))
  (import "env" "vx_log" (func $vx_log (param i32)))
  (memory 1)
)
""")

# Register host functions in the linker with the exact import names.
for name, fn, ty in [
    ("vx_pin_register", vx_pin_register, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_pin_read", vx_pin_read, wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_pin_write", vx_pin_write, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [])),
    ("vx_i2c_attach", vx_i2c_attach, wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_timer_create", vx_timer_create, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [wasmtime.ValType.i32()])),
    ("vx_timer_start", vx_timer_start, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i64(), wasmtime.ValType.i32()], [])),
    ("vx_timer_stop", vx_timer_stop, wasmtime.FuncType([wasmtime.ValType.i32()], [])),
    ("vx_log", vx_log, wasmtime.FuncType([wasmtime.ValType.i32()], [])),
]:
    linker.define(store, "env", name, wasmtime.Func(store, ty, fn))

module = wasmtime.Module.from_file(store.engine, WASM)
memtype = wasmtime.MemoryType(wasmtime.Limits(2, None))
shared_mem = wasmtime.Memory(store, memtype)
linker.define(store, "env", "memory", shared_mem)
inst = linker.instantiate(store, module)
mem = shared_mem
mem_holder["mem"] = mem
table = inst.exports(store)["__indirect_function_table"]

inst.exports(store)["chip_setup"](store)
print("registered pins:", sorted(pin_handles.keys()))
assert "PWM0" in pin_handles and "PWM15" in pin_handles and "SCL" in pin_handles
assert i2c_cbs["address"] == 0x40, f"bad i2c addr {i2c_cbs['address']}"

def i2c_call(cb, *args):
    fn = table.get(store, i2c_cbs[cb])
    return fn(store, i2c_cbs["user_data"], *args)

# --- I2C: replicate Adafruit_PWMServoDriver::begin() + setPWMFreq(50) ---
i2c_call("on_connect", 0x40, 0)             # write transaction
i2c_call("on_write", 0x00)                  # pointer = MODE1
i2c_call("on_write", 0x00)                  # MODE1 = 0 (AI off)
i2c_call("on_stop")
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x00); i2c_call("on_write", 0x10)   # MODE1 = SLEEP
i2c_call("on_stop")
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0xFE); i2c_call("on_write", 121)    # PRESCALE = 121
i2c_call("on_stop")
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x00); i2c_call("on_write", 0xA0)   # MODE1 = RESTART|AI
i2c_call("on_stop")

# setPWM(0, 0, 150): burst-write 4 regs at 0x06 (auto-increment on)
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x06)
i2c_call("on_write", 0x00)   # ON_L
i2c_call("on_write", 0x00)   # ON_H
i2c_call("on_write", 150)    # OFF_L
i2c_call("on_write", 0x00)   # OFF_H
i2c_call("on_stop")

# fire 400 frame ticks, count PWM0 HIGH ticks
timer_fn = table.get(store, timer_cb_index[0])
timer_ud = timer_cb_index[1]
high = 0
for t in range(400):
    timer_fn(store, timer_ud)
    # inspect last write
for name, v in pin_writes:
    pass
# count HIGH windows by replaying: instead, track level changes
levels = []
pin_writes.clear()
for t in range(400):
    timer_fn(store, timer_ud)
    if pin_writes:
        levels.append(pin_writes[-1][1])
    else:
        levels.append(levels[-1] if levels else 0)
high = sum(levels)
print(f"PWM0 HIGH ticks: {high}/400 (expected ~14)")
assert 10 <= high <= 18, f"PWM0 duty wrong: {high}"

# --- second channel sanity: setPWM(1, 0, 300) -> ~29 ticks ---
i2c_call("on_connect", 0x40, 0)
i2c_call("on_write", 0x0A)
i2c_call("on_write", 0x00); i2c_call("on_write", 0x00)
i2c_call("on_write", 0x2C); i2c_call("on_write", 0x01)   # 300
i2c_call("on_stop")
pin_writes.clear(); levels = []
for t in range(400):
    timer_fn(store, timer_ud)
    if pin_writes and pin_writes[-1][0] == "PWM1":
        levels.append(pin_writes[-1][1])
    else:
        levels.append(levels[-1] if levels else 0)
high1 = sum(levels)
print(f"PWM1 HIGH ticks: {high1}/400 (expected ~29)")
assert 25 <= high1 <= 33, f"PWM1 duty wrong: {high1}"

print("ALL TESTS PASSED")
