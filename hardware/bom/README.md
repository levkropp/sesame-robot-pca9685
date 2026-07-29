# Bill of Materials

Every part required to assemble Sesame is cataloged here. Pick the wiring strategy that fits your parts bin, then follow the build flow in [docs/build-guide/README.md](../../docs/build-guide/README.md).

> [!NOTE]
> Amazon links below point to representative search results so you can choose local suppliers or equivalent listings. Pricing and availability change frequently. If you don't mind waiting shipping times you can also order direct from manufacturer for much lower rates.


## Core Electronics (Both Builds)

| Item | Qty | Notes | Source |
| --- | --- | --- | --- |
| MG90S all-metal micro servos (180 Deg) | 8 (buy 10 for spares) | Primary hip/leg actuators; includes servo horns but keep extras | [Amazon](https://www.amazon.com/s?k=mg90s+metal+gear+servo+pack+of+8) |
| 0.96" SSD1306 I2C OLED | 1 | 128x64 display that slides into the top cover slot | [Amazon](https://www.amazon.com/s?k=0.96%22+I2C+OLED+SSD1306) |
| USB-C data/power cable | 1 | Needs to carry 5V/3A for flashing and tethered mode | [Amazon](https://www.amazon.com/s?k=usb+c+cable+60w) |
| Rocker power switch (KCD1, panel mount) | 1 | Snaps into the top cover cutout | [Amazon](https://www.amazon.com/s?k=KCD1+mini+rocker+switch+2+pin) |
| 22AWG silicone wire kit | 1 | Power/ground bus lines | [Amazon](https://www.amazon.com/s?k=22awg+silicone+wire+kit) |
| 30AWG silicone wire kit | 1 | Signal leads and dense harnessing | [Amazon](https://www.amazon.com/s?k=30awg+silicone+wire) |
| Heat-shrink assortment | 1 | Insulate OLED, switch, and battery joints | [Amazon](https://www.amazon.com/s?k=heat+shrink+tubing+kit) |
| Small zip ties | 1 pack | Bundling wires inside the frame | [Amazon](https://www.amazon.com/s?k=mini+zip+ties) |

## Wiring Option A0 – ESP32-S3 Mini / PCA9685 Driver Board (This Fork, Recommended — No Soldering at All)

| Item | Qty | Notes | Source |
| --- | --- | --- | --- |
| Waveshare ESP32-S3-Zero-M (ESP32-S3 Mini) | 1 (sold as 3-pack) | Pre-soldered headers guaranteed in the listing; dual-core ESP32-S3FH4R2, 4MB flash / 2MB PSRAM, USB-C | [Amazon.ca $39.99 for 3 (~$13.30 each)](https://www.amazon.ca/dp/B0G43ZYD8G) |
| PCA9685 16-Channel PWM Servo Driver | 1 | Pre-soldered servo headers; servos plug straight in, only 4 I2C wires to the S3 Mini | [Amazon.ca ~$14 CAD](https://www.amazon.ca/PCA9685-Interface-Controller-Compatible-Raspberry/dp/B07RMTN4NZ) |
| **Phase 1 (tethered, recommended for first build):** USB-C 5V/3A wall adapter | 1 | A 5V/3A source IS the regulated rail — no buck converter needed while tethered | Any quality 5V/3A USB-C supply |
| **Phase 1:** USB-C breakout with screw terminals | 1 | Gets 5V from the wall adapter into the PCA9685's screw terminal without soldering | [Amazon](https://www.amazon.com/s?k=usb+c+breakout+screw+terminal) |
| **Phase 2 (battery, add later):** LM2596-class buck, ~4-38V input, 5V/3A output | 1 | **Required for battery** — the PCA9685 does NOT regulate the servo rail; 7.4V would overvolt the MG90S (6V max). Choose input range that goes down to ~7V: a 2S pack spends most of its discharge BELOW 8V, so "8-35V input" modules (e.g. the DROK 8-35V) drop out for most of the battery's life. LED display version lets you verify output is exactly 5.0V before connecting servos | [Amazon.ca $19.99 for 2 (4-38V, w/ display)](https://www.amazon.ca/dp/B085T73CSD) |
| **Phase 2:** XH2.54 pre-wired pigtail | 1 | Mates the Bambu battery connector to the switch/buck without cutting the pack's stock leads (or crimp your own from the JST-XH kit) | [Amazon](https://www.amazon.com/s?k=xh2.54+pigtail+cable) |
| **Phase 2:** Lever wire connectors (Wago 221 style) | 2-3 | Zero-solder splices for the battery→switch→buck chain | [Amazon](https://www.amazon.com/s?k=wago+221+lever+connectors) |

**Phase 1 power chain (tethered, no buck):** USB-C 5V/3A wall adapter → USB-C screw-terminal breakout → PCA9685 screw terminal (servo rail) → tap V+ from the PCA9685 control header (Dupont) → S3 Mini 5V pin. The S3 Mini's own USB-C port stays free for flashing — but unplug the V+ tap whenever USB is connected (never power the MCU from both at once).

**Phase 2 power chain (battery, purely additive):** unplug the USB-C breakout, then: Bambu battery (XH2.54) → pre-wired XH2.54 pigtail → lever connector → pre-wired rocker switch → lever connector → buck input → buck 5V output → the *same* PCA9685 screw terminal + the *same* V+ tap to the S3 Mini. Nothing about the servo or logic wiring changes — the battery+buck simply replaces the wall adapter+breakout at the exact same two screw terminals. The only part of the whole build that may still need an iron is the OLED's 4-pin header — many 0.96" SSD1306 modules ship with the pins included but unsoldered; either solder that one trivial 4-pin row or buy a pre-pinned OLED variant.

See [`docs/pca9685-fork/README.md`](../../docs/pca9685-fork/README.md) for the full wiring and firmware writeup. Replaces the protoboard + 8x header pins from Option A below — you don't need those if you're using this option. A Lolin/WeMos ESP32-S2 Mini also works with this fork (firmware has a pin block for it) but S2 Minis don't reliably ship with pre-soldered headers, which is why the S3-Zero-M is the recommendation here.

> [!NOTE]
> **Battery alternative for this option:** the Bambu Lab 7.4V pack is just two 14500 Li-ion cells in series (2S), so two quality 3.7V 14500 cells in a 2S holder works identically — *with caveats*: use two identical new cells (same brand/model/capacity), add a **2S BMS/protection board** (~$5-15, over-discharge + short protection), and solve charging before you build: either a 2S balance charger (the Bambu charger is exactly this, and it matches the XH2.54 connector), a generic 2S charger, or charge the cells individually outside the robot. **Never charge a 2S series pack through a single-cell (TP4056-style) USB charger board** — that's a fire risk. 14500 is AA-sized Li-ion; do not confuse it with 1.2V NiMH AAs, and never charge Li-ion cells in a plain NiMH AA holder.
>
> **Other battery configurations — the rule is the buck converter's input window (5–12V), since servos never see raw battery voltage (MG90S max is 6V):**
> - **2× 18650 in series (7.4V):** voltage is fine, but the pack (~65×36×18mm, ~90-100g) does not fit the frame's battery bay (sized for the ~53×29×16mm 14500 pack) and is heavy for 9g servos to carry — only worth it with a frame redesign.
> - **5× AAA NiMH (6.0V):** workable through the buck converter; near the bottom of the buck's input range when discharged, so pick a buck rated for ≥5V input (or buck-boost).
> - **5× AAA alkaline (7.5V fresh):** fits the voltage window on paper but alkaline AAAs sag badly under multi-servo load bursts — expect brownouts/resets while walking. Not recommended.
> - **5× 10440 Li-ion (18.5V):** DANGER — far above the 12V buck input max. Will damage the buck converter and everything behind it. If using AAA-size Li-ion (10440), only ever 2 in series (7.4V), and per upstream's warning, never charge them in a plain AAA holder.

## Wiring Option A – S2 Mini / Hand-Wired Harness (Upstream Default)

| Item | Qty | Notes | Source |
| --- | --- | --- | --- |
| Lolin/WeMos ESP32-S2 Mini | 1 | Native USB-C, fits on perfboard for the hand-wired build | [Amazon](https://www.amazon.com/s?k=esp32+s2+mini) |
| Small protoboard (approx. 5×7 cm) | 1 | Hosts the header matrix and rails | [Amazon](https://www.amazon.com/s?k=prototype+perfboard) |
| 3-pin male headers | 8 | Build the servo breakout; match spacing to MG90 plugs | [Amazon](https://www.amazon.com/s?k=pin+header+strip) |
| Buck converter (5–12 V in to stable 5V/3A out) | 1 | Powers motors + MCU when using batteries | [Amazon](https://www.amazon.com/s?k=3a+dc+dc+buck+converter+module) |

## Wiring Option B – Sesame Distro Board V3/V2 (Included in Build Kits)

> [!NOTE]
> If you purchased a Sesame Build Kit, your V2 Distro Board is already assembled, pre-flashed, and included. You don't need to order these parts separately.

| Item | Qty | Notes | Source |
| --- | --- | --- | --- |
| Sesame Distro Board V3/V2 PCB | 1 | Fully SMD design. Order with PCBway assembly service or attempt advanced hand soldering. See [ordering guide](/hardware/pcb/README.md) | [GitHub](/hardware/pcb/README.md) |

## Wiring Option C – Sesame Distro Board V1 / ESP32-DevKitC-32E (Legacy)

> [!CAUTION]
> V1 is now phased out but still supported. Only choose this if you already have a V1 board.

| Item | Qty | Notes | Source |
| --- | --- | --- | --- |
| ESP32-DevKitC-32E (ESP32-WROOM-32) | 1 | Base board the Distro Board V1 stacks on. This one is very tricky because its a very specific board. You can use the 32E with the floating pcb antenna OR you can use the 32U but you have to route an antenna inside. | [Amazon](https://www.amazon.com/s?k=ESP32+DevKitC+32) |
| Sesame Distro Board V1 PCB | 1 | Order `Gerber_Sesame-Distro-Board_PCB_Sesame-Distro-Board_V1.zip` via PCBway | [GitHub](/hardware/pcb/README.md) |
| 5V buck converter (same spec as above) | 1 | Mounts on the distro board pads | [Amazon](https://www.amazon.com/s?k=3a+dc+dc+buck+converter+module) |
| 1000 µF electrolytic capacitor | 1 | Smooths output voltage on buck converter; 10V+ rating recommended | [Amazon](https://www.amazon.com/s?k=1000uf+electrolytic+capacitor) |
| 4-pin JST-XH or PH header | 1 | Optional external connector footprint on PCB | [Amazon](https://www.amazon.com/s?k=jst+xh+4+pin+kit) |
| 2-pin screw terminal (2.54 mm pitch) | 1 | Optional battery input on PCB | [Amazon](https://www.amazon.com/s?k=2+pin+screw+terminal+block+2.54mm+pitch) |
| M2.5 × 5 mm male-female standoffs | 4 | Elevate the PCB over the DevKit mounting holes | [Amazon](https://www.amazon.com/s?k=m2.5+male+female+standoff+5mm) |

## Power Sources & Connectors

| Item | Qty | Notes | Source |
| --- | --- | --- | --- |
| Bambu Lab 14500 7.4V 800mAh Li-ion Battery | 1 | Recommended wireless pack; cheap, effective, designed to fit inside the new internal frame. | [Bambu Lab](https://us.store.bambulab.com/products/14500-7-4v-800mah-li-ion-battery-1pcs) |
| Bambu Lab 7.4V Lithium battery charger | 1 | Matching charger for the 14500 battery with XH2.54 connector. | [Bambu Lab](https://us.store.bambulab.com/products/7-4v-lithium-battery-charger-with-xh2-54-connector-1pcs?id=593290727051776002) |
| XH2.54 female pigtail | 1 | Interface battery to switch/PCB without cutting stock leads (V3 requires soldering). | [Amazon](https://www.amazon.com/s?k=xh2.54+pigtail+cable) |

## Fasteners & Mechanical Hardware

| Item | Qty | Usage | Amazon |
| --- | --- | --- | --- |
| M2 × 5 mm self-threading screws | ~40 | All plastic joints, OLED retention, motor mounts, and covers (Can just get a variety pack) | [Amazon](https://www.amazon.com/s?k=m2+self+tapping+screws+kit) |
| M2.5 × 5mm machine screws | 10 | Servo horn attachment to servo shafts only. Included servo horn screws are usually too short. | [Amazon](https://www.amazon.com/s?k=m2+machine+screw+kit) |

## 3D Printed Parts

Print the 11-part part set outlined in [printing/README.md](../printing/README.md). STL and CAD sources live under `hardware/printing/`.

## Consumables & Tools Checklist

| Item | Notes | Source |
| --- | --- | --- |
| Leaded solder (0.6–0.8 mm) | Easier flow for dense perfboard work | [Amazon](https://www.amazon.com/s?k=63%2F37+solder+0.8mm) |
| Flux pen | Protects pads on the perfboard and PCB | [Amazon](https://www.amazon.com/s?k=flux+pen) |
| Solder wick / pump | For rework on the OLED pins | [Amazon](https://www.amazon.com/s?k=solder+wick) |
| Small flush cutters | Trim servo leads, perfboard traces, or supports | [Amazon](https://www.amazon.com/s?k=flush+cutters) |
| Precision screwdriver set | Needed for self-tapping M2 hardware | [Amazon](https://www.amazon.com/s?k=precision+screwdriver+set) |

## Power & Safety Notes

- Sesame needs at least 5 V at 3 A available at the rails. 
- **Lolin S2 Mini:** Can be powered via USB-C PD (5V/3A capable) for tethered operation, or via battery + buck converter.
- **Distro Board V3/V2:** Supports both USB-C PD (5V/3A) for tethered operation AND battery + buck converter. Included in all Sesame Build Kits.
- **Distro Board V1 (Legacy):** Cannot run on tethered USB-C power due to design limitations. Must use battery + buck converter for operation.
- When battery powering either build, route the pack through the rocker switch and buck converter before it touches the rails, mirroring the schematic in [docs/wiring-guide/README.md](../../docs/wiring-guide/README.md).
- **Never cut the factory battery connector off the pack.** Instead, create adapter pigtails using XT30 or JST RCY leads so the pack remains chargeable.
- A Bambu Lab 14500 7.4V 800mAh Li-ion battery fits the new stock battery cavity (V3 requires printing the new internal frame).
- **Always apply heat shrink tubing to connectors**. Be extremely careful when cutting and soldering battery connectors. If you are still using the legacy 10440 solution make sure the cells are removed during soldering.
