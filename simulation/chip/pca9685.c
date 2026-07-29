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
 * PWM generation is EVENT-DRIVEN, not tick-driven: a single one-shot timer
 * is re-armed to the soonest upcoming edge (rise or fall) across all
 * channels, using vx_sim_now_nanos() as the time base. Pulse widths land
 * within scheduler jitter (~50 µs) of the commanded value instead of
 * snapping to a tick grid, and the chip costs ~1 timer fire per edge
 * (~16/20 ms for 8 channels) instead of a constant 4-20 kHz tick storm —
 * which matters inside the velxio QEMU backend where every fire needs the
 * IO-thread lock.
 *
 * Not modeled (v1): the OE output-enable pin (outputs are always enabled),
 * SUBADR/ALLCALL addresses, external clock input, and non-50Hz frame rates.
 *
 * License: MIT. Written against the MIT-licensed velxio-chip.h SDK.
 */

#include "velxio-chip.h"
#include <stdio.h>
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

#define FRAME_NS       20000000ULL   /* 20 ms @ 50 Hz */
#define MIN_ARM_NS     2000ULL       /* clamp one-shot arm delay (2 µs) */

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

  /* event-driven PWM state */
  uint64_t on_ns[16];      /* rise offset within the 20 ms frame */
  uint64_t off_ns[16];     /* fall offset within the 20 ms frame */
  uint8_t  has_pwm[16];    /* channel produces edges (off>on && off>0) */
  int      level[16];      /* current output level, -1 = not yet driven */
  uint64_t frame_epoch;    /* sim-time anchor the schedule is built from */
  int      epoch_set;      /* 1 once the global frame clock has been anchored */
  int      timer_armed;    /* a one-shot is currently pending */
  int      armed_ch;       /* which channel the pending edge belongs to */
  int      armed_level;    /* level that edge will apply */
  uint32_t armed_gen;      /* config generation at arm time */
  uint32_t config_gen;     /* bumped on every PWM-relevant register write */
} chip_state_t;

static const char* const PWM_NAMES[16] = {
  "PWM0", "PWM1", "PWM2",  "PWM3",  "PWM4",  "PWM5",  "PWM6",  "PWM7",
  "PWM8", "PWM9", "PWM10", "PWM11", "PWM12", "PWM13", "PWM14", "PWM15",
};

static uint64_t cnt_to_ns(uint16_t cnt) {
  return ((uint64_t)cnt * FRAME_NS) >> 12;
}

static void set_level(chip_state_t* s, int ch, int level) {
  if (s->level[ch] != level) {
    vx_pin_write(s->pwm[ch], level);
    s->level[ch] = level;
  }
}

/* Set every channel's level from the current frame phase. Called before
 * scheduling so a channel configured mid-frame starts at the right level
 * instead of waiting a full frame for a wrapped rise edge. */
static void sync_levels_to_phase(chip_state_t* s) {
  uint64_t now = vx_sim_now_nanos();
  uint64_t phase = (now - s->frame_epoch) % FRAME_NS;
  for (int ch = 0; ch < 16; ch++) {
    if (!s->has_pwm[ch]) continue;
    uint64_t on = s->on_ns[ch], off = s->off_ns[ch];
    int lvl;
    if (on < off) lvl = (phase >= on && phase < off) ? VX_HIGH : VX_LOW;
    else          lvl = (phase >= on || phase < off) ? VX_HIGH : VX_LOW;
    set_level(s, ch, lvl);
  }
}

/* Arm the one-shot timer for the soonest edge across all channels.
 * Returns 1 if an edge was scheduled, 0 if the bus is idle (no PWM). */
static int schedule_next(chip_state_t* s) {
  if (s->regs[REG_MODE1] & MODE1_SLEEP) {
    for (int ch = 0; ch < 16; ch++) set_level(s, ch, VX_LOW);
    vx_timer_stop(s->timer);
    s->timer_armed = 0;
    return 0;
  }

  sync_levels_to_phase(s);

  uint64_t now = vx_sim_now_nanos();
  uint64_t best = ~0ULL;
  int best_ch = -1, best_level = VX_LOW;

  for (int ch = 0; ch < 16; ch++) {
    if (!s->has_pwm[ch]) continue;
    for (int e = 0; e < 2; e++) {
      uint64_t in_frame = (e == 0) ? s->on_ns[ch] : s->off_ns[ch];
      uint64_t base = s->frame_epoch + in_frame;
      uint64_t t;
      if (now < base) {
        t = base;
      } else {
        uint64_t k = (now - base) / FRAME_NS + 1;
        t = base + k * FRAME_NS;
      }
      if (t < best) {
        best = t;
        best_ch = ch;
        best_level = (e == 0) ? VX_HIGH : VX_LOW;
      }
    }
  }

  if (best_ch < 0) {
    s->timer_armed = 0;
    return 0;
  }

  uint64_t wait = best - now;
  if (wait < MIN_ARM_NS) wait = MIN_ARM_NS;
  vx_timer_start(s->timer, wait, false);   /* one-shot */
  s->timer_armed = 1;
  s->armed_ch = best_ch;
  s->armed_level = best_level;
  s->armed_gen = s->config_gen;
  return 1;
}

static void on_edge(void* ud) {
  chip_state_t* s = (chip_state_t*)ud;
#ifdef DEBUG_EDGE_LOG
  if (s->timer_armed && s->armed_ch >= 0) {
    char buf[80];
    snprintf(buf, sizeof(buf), "edge ch%d -> %d @ %llu ns",
             s->armed_ch, s->armed_level, (unsigned long long)vx_sim_now_nanos());
    vx_log(buf);
  }
#endif
  /* Apply the armed edge only if the config hasn't changed since arming;
   * either way, recompute the schedule from the current registers. */
  if (s->timer_armed && s->armed_ch >= 0 && s->armed_gen == s->config_gen) {
    set_level(s, s->armed_ch, s->armed_level);
  }
  s->timer_armed = 0;
  schedule_next(s);
}

/* Re-read one channel's 4 phase registers into decoded + scheduled form. */
static void sync_channel(chip_state_t* s, int ch) {
  uint8_t base = (uint8_t)(0x06 + 4 * ch);
  s->on[ch]       = (uint16_t)(s->regs[base] | ((s->regs[base + 1] & 0x0F) << 8));
  s->off[ch]      = (uint16_t)(s->regs[base + 2] | ((s->regs[base + 3] & 0x0F) << 8));
  s->full_on[ch]  = (s->regs[base + 1] & 0x10) ? 1 : 0;
  s->full_off[ch] = (s->regs[base + 3] & 0x10) ? 1 : 0;

  s->on_ns[ch]  = cnt_to_ns(s->on[ch]);
  s->off_ns[ch] = cnt_to_ns(s->off[ch]);

  if (s->full_on[ch]) {
    s->has_pwm[ch] = 0;
    set_level(s, ch, VX_HIGH);
  } else if (s->full_off[ch]) {
    s->has_pwm[ch] = 0;
    set_level(s, ch, VX_LOW);
  } else if (s->off[ch] == 0 || s->off[ch] == s->on[ch]) {
    s->has_pwm[ch] = 0;
    set_level(s, ch, VX_LOW);
  } else {
    if (!s->has_pwm[ch] && !s->epoch_set) {
      /* The frame clock is GLOBAL (the real chip has one prescaler for all
       * channels): anchor it the first time any channel starts PWMing and
       * never reset it — resetting per-channel shifts every other channel's
       * pulse times by the inter-write delay. Channels joining mid-frame get
       * phase-synced by sync_levels_to_phase instead. */
      s->epoch_set = 1;
      s->frame_epoch = vx_sim_now_nanos();
    }
    s->has_pwm[ch] = 1;
  }

  s->config_gen++;
  schedule_next(s);
}

static void apply_all_led(chip_state_t* s) {
  uint16_t on  = (uint16_t)(s->regs[REG_ALL_ON_L] | ((s->regs[REG_ALL_ON_H] & 0x0F) << 8));
  uint16_t off = (uint16_t)(s->regs[REG_ALL_OFF_L] | ((s->regs[REG_ALL_OFF_H] & 0x0F) << 8));
  uint8_t fon  = (s->regs[REG_ALL_ON_H] & 0x10) ? 1 : 0;
  uint8_t foff = (s->regs[REG_ALL_OFF_H] & 0x10) ? 1 : 0;
  for (int i = 0; i < 16; i++) {
    s->on[i] = on; s->off[i] = off;
    s->full_on[i] = fon; s->full_off[i] = foff;
    s->on_ns[i] = cnt_to_ns(on); s->off_ns[i] = cnt_to_ns(off);
    if (fon)          { s->has_pwm[i] = 0; set_level(s, i, VX_HIGH); }
    else if (foff)    { s->has_pwm[i] = 0; set_level(s, i, VX_LOW); }
    else if (off == 0 || off == on) { s->has_pwm[i] = 0; set_level(s, i, VX_LOW); }
    else              { s->has_pwm[i] = 1; }
  }
  s->config_gen++;
  schedule_next(s);
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
  } else if (reg == REG_MODE1) {
    /* sleep assert -> schedule_next drops outputs & stops the timer;
       sleep clear (wake) -> re-arm from current time. Both handled inside. */
    schedule_next(s);
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
  for (int i = 0; i < 16; i++) s->level[i] = -1;
  s->armed_ch = -1;
  s->frame_epoch = vx_sim_now_nanos();

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

  s->timer = vx_timer_create(on_edge, s);

  vx_log("PCA9685 ready (I2C 0x40, 16ch event-driven PWM @ 50Hz frame)");
}
