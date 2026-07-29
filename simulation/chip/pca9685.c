/*
 * pca9685.c — PCA9685 16-channel 12-bit PWM driver (I2C), velxio custom chip.
 *
 * Models the parts of the chip the Adafruit_PWMServoDriver library actually
 * uses (which is what most Arduino/ESP32 servo projects drive):
 *
 *   - I2C slave at 0x40 (default address), register pointer + auto-increment
 *     (honors MODE1 bit5 AI; the Adafruit lib sets AI=1 during begin()).
 *   - MODE1 sleep: outputs hold LOW while the SLEEP bit is set.
 *   - LEDn_ON / LEDn_OFF 12-bit phase registers (0x06..0x45) and the
 *     ALL_LED_ON / ALL_LED_OFF broadcast registers (0xFA..0xFD).
 *   - Full-ON (ON_H bit4) and full-OFF (OFF_H bit4) special cases.
 *   - PRESCALE register is accepted (stored) — the sim always generates a
 *     20 ms frame like a 50 Hz servo signal, which is all the canvas servos
 *     care about.
 *
 * PWM output: a repeating 50 µs timer divides the 20 ms frame into 400
 * ticks; each channel drives HIGH while the frame tick is inside its
 * [ON, OFF) window. Output edges therefore have ≤50 µs quantization
 * (~±2° on a 180° servo) — plenty for visualization.
 *
 * Not modeled (v1): the OE output-enable pin (outputs are always enabled),
 * SUBADR/ALLCALL addresses, external clock input, and non-50Hz frame rates.
 *
 * License: MIT. Written against the MIT-licensed velxio-chip.h SDK.
 */

#include "velxio-chip.h"
#include <stdlib.h>
#include <string.h>

#define PCA_ADDR       0x40

#define REG_MODE1      0x00
#define REG_ALL_ON_L   0xFA
#define REG_ALL_ON_H   0xFB
#define REG_ALL_OFF_L  0xFC
#define REG_ALL_OFF_H  0xFD
#define REG_PRESCALE   0xFE

#define MODE1_AI       0x20
#define MODE1_SLEEP    0x10

#define TICKS_PER_FRAME 400          /* 20 ms / 50 µs */
#define TIMER_NS        50000ULL

typedef enum { ST_IDLE, ST_HAS_PTR } i2c_state_t;

typedef struct {
  vx_pin   pwm[16];
  vx_timer timer;
  uint8_t  regs[256];
  uint8_t  ptr;
  i2c_state_t state;
  uint16_t on[16];
  uint16_t off[16];
  uint8_t  full_on[16];
  uint8_t  full_off[16];
  int      last[16];       /* last driven level, -1 = not yet driven */
  uint32_t tick;
} chip_state_t;

static const char* const PWM_NAMES[16] = {
  "PWM0", "PWM1", "PWM2",  "PWM3",  "PWM4",  "PWM5",  "PWM6",  "PWM7",
  "PWM8", "PWM9", "PWM10", "PWM11", "PWM12", "PWM13", "PWM14", "PWM15",
};

/* Re-read one channel's 4 phase registers into decoded form. */
static void sync_channel(chip_state_t* s, int ch) {
  uint8_t base = (uint8_t)(0x06 + 4 * ch);
  s->on[ch]       = (uint16_t)(s->regs[base] | ((s->regs[base + 1] & 0x0F) << 8));
  s->off[ch]      = (uint16_t)(s->regs[base + 2] | ((s->regs[base + 3] & 0x0F) << 8));
  s->full_on[ch]  = (s->regs[base + 1] & 0x10) ? 1 : 0;
  s->full_off[ch] = (s->regs[base + 3] & 0x10) ? 1 : 0;
}

static void apply_all_led(chip_state_t* s) {
  uint16_t on  = (uint16_t)(s->regs[REG_ALL_ON_L] | ((s->regs[REG_ALL_ON_H] & 0x0F) << 8));
  uint16_t off = (uint16_t)(s->regs[REG_ALL_OFF_L] | ((s->regs[REG_ALL_OFF_H] & 0x0F) << 8));
  uint8_t fon  = (s->regs[REG_ALL_ON_H] & 0x10) ? 1 : 0;
  uint8_t foff = (s->regs[REG_ALL_OFF_H] & 0x10) ? 1 : 0;
  for (int i = 0; i < 16; i++) {
    s->on[i] = on; s->off[i] = off;
    s->full_on[i] = fon; s->full_off[i] = foff;
  }
}

static void on_frame_tick(void* ud) {
  chip_state_t* s = (chip_state_t*)ud;
  const int sleeping = (s->regs[REG_MODE1] & MODE1_SLEEP) != 0;

  for (int ch = 0; ch < 16; ch++) {
    int level;
    if (sleeping || s->full_off[ch]) {
      level = VX_LOW;
    } else if (s->full_on[ch]) {
      level = VX_HIGH;
    } else {
      /* map 12-bit phase counts onto frame ticks: *400/4096 = *25/256 */
      uint32_t on_t  = ((uint32_t)s->on[ch]  * 25u) >> 8;
      uint32_t off_t = ((uint32_t)s->off[ch] * 25u) >> 8;
      if (off_t == on_t) {
        level = VX_LOW;
      } else if (off_t > on_t) {
        level = (s->tick >= on_t && s->tick < off_t) ? VX_HIGH : VX_LOW;
      } else { /* window wraps the end of the frame */
        level = (s->tick >= on_t || s->tick < off_t) ? VX_HIGH : VX_LOW;
      }
    }
    if (level != s->last[ch]) {
      vx_pin_write(s->pwm[ch], level);
      s->last[ch] = level;
    }
  }
  s->tick = (s->tick + 1) % TICKS_PER_FRAME;
}

static bool on_connect(void* ud, uint8_t addr, bool is_read) {
  chip_state_t* s = (chip_state_t*)ud;
  (void)addr;
  if (!is_read) s->state = ST_IDLE;   /* next byte = register pointer */
  return true;
}

static bool on_write(void* ud, uint8_t byte) {
  chip_state_t* s = (chip_state_t*)ud;
  if (s->state == ST_IDLE) {
    s->ptr = byte;
    s->state = ST_HAS_PTR;
    return true;
  }

  uint8_t reg = s->ptr;
  s->regs[reg] = byte;

  /* keep decoded channel state in sync */
  if (reg >= 0x06 && reg <= 0x45) {
    sync_channel(s, (reg - 0x06) / 4);
  } else if (reg >= REG_ALL_ON_L && reg <= REG_ALL_OFF_H) {
    apply_all_led(s);
  }

  if (s->regs[REG_MODE1] & MODE1_AI) s->ptr = (uint8_t)(s->ptr + 1);
  return true;
}

static uint8_t on_read(void* ud) {
  chip_state_t* s = (chip_state_t*)ud;
  uint8_t b = s->regs[s->ptr];
  if (s->regs[REG_MODE1] & MODE1_AI) s->ptr = (uint8_t)(s->ptr + 1);
  return b;
}

static void on_stop(void* ud) {
  chip_state_t* s = (chip_state_t*)ud;
  s->state = ST_IDLE;
}

void chip_setup(void) {
  chip_state_t* s = (chip_state_t*)calloc(1, sizeof(chip_state_t));
  for (int i = 0; i < 16; i++) s->last[i] = -1;

  for (int i = 0; i < 16; i++) {
    s->pwm[i] = vx_pin_register(PWM_NAMES[i], VX_OUTPUT_LOW);
  }

  vx_i2c_config cfg = {
    .address    = PCA_ADDR,
    .scl        = vx_pin_register("SCL", VX_INPUT),
    .sda        = vx_pin_register("SDA", VX_INPUT),
    .on_connect = on_connect,
    .on_read    = on_read,
    .on_write   = on_write,
    .on_stop    = on_stop,
    .user_data  = s,
  };
  vx_i2c_attach(&cfg);

  /* Power-on state of a real PCA9685: MODE1 = 0x11 (SLEEP | ALLCALL). */
  s->regs[REG_MODE1] = 0x11;

  s->timer = vx_timer_create(on_frame_tick, s);
  vx_timer_start(s->timer, TIMER_NS, true);

  vx_log("PCA9685 ready (I2C 0x40, 16ch PWM @ 50Hz frame)");
}
