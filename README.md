# The Sesame Robot Project — PCA9685 Edition (Fork)
___

> **This is a fork of [dorianborian/sesame-robot](https://github.com/dorianborian/sesame-robot).**
> It swaps the hardest soldering step in the hand-wired build — hand-bridging a
> 3×8 pin header array for the servo power/ground/signal lines — for a single **$14 CAD
> plug-and-play PCA9685 servo driver board**, and pairs it with a **Waveshare ESP32-S3-Zero-M**
> (pre-soldered headers, guaranteed) so the whole electronics stack needs *zero* soldering.
> Servos plug straight into pre-soldered header pins on the driver board; no perfboard,
> no bus wire, no soldering to the servo harness at all.
> See [`docs/pca9685-fork/README.md`](docs/pca9685-fork/README.md) for
> the full writeup, or run the [`website/`](website/) explainer site locally.
> **New:** you can also *run the whole build virtually* before wiring anything —
> [`simulation/`](simulation/) contains a [Velxio](https://github.com/davidmonterocrespo24/velxio)
> project (`.vlx`) that boots the real firmware on an emulated ESP32-S3 with a
> [custom PCA9685 chip](https://github.com/levkropp/pca9685-velxio), 8 virtual
> servos, and the OLED face, drivable from the Serial Monitor.
> All credit for the original design, firmware, and hardware goes to
> [Dorian Todd](https://www.doriantodd.com/) — this fork only changes how the servos
> are wired and driven, plus which microcontroller board is recommended.

___
![License](https://img.shields.io/badge/License-APACHE2.0-yellow)
[![validate](https://github.com/levkropp/sesame-robot-pca9685/actions/workflows/validate.yml/badge.svg)](https://github.com/levkropp/sesame-robot-pca9685/actions/workflows/validate.yml)
[![pages](https://github.com/levkropp/sesame-robot-pca9685/actions/workflows/pages.yml/badge.svg)](https://levkropp.github.io/sesame-robot-pca9685/)
![Microcontroller](https://img.shields.io/badge/Microcontroller-ESP32-blue)
![Firmware](https://img.shields.io/badge/Firmware-C%2B%2B-blue?logo=c%2B%2B)
![IDE](https://img.shields.io/badge/IDE-Arduino-00979D?logo=arduino&logoColor=white)
![GitHub stars](https://img.shields.io/github/stars/dorianborian/sesame-robot?style=social)
![GitHub forks](https://img.shields.io/github/forks/dorianborian/sesame-robot?style=social)

<img width="100%" height="728" alt="sesame-cover" src="https://github.com/user-attachments/assets/f0cc6ad0-135b-4515-8750-900f224ed7ae" />

<p align="center">
  <a href="https://www.youtube.com/watch?v=NIgoQVQF_Ng">
    <img src="https://github.com/user-attachments/assets/1663e022-0680-4053-97b4-53e669a6f07d" width="49%" alt="tutorial-button">
  </a>
  <a href="https://discord.gg/XDXkhQd8bC">
    <img src="https://github.com/user-attachments/assets/378fcb48-5b12-4b46-9dcb-452432d49913" width="49%" alt="discord-button">
  </a>
</p>

___

**Greetings, from your new best friend.**

Sesame is an accessible Open-Source robotics project based on the ESP32 microcontroller system, with an emphasis on expression and movement. 
This project is designed for makers and engineers of all skill levels! Sesame offers a dynamic platform designed to start working with walking robots. 
To build a sesame robot, you will need basic soldering skills, $50-60 in hardware components, access to a 3D printer, and a basic understanding of Arduino IDE.

This repository contains the CAD design files, STL files, build and wiring guides, and the base/expanded firmware for the ESP32-based controller. 
There is also some included debugging firmware that may be helpful in getting your Sesame up and running.

## Features

*   **Quadruped Design:** Uses 8 servo motors (2 per leg) to achieve roughly 8 total degrees of freedom.
*   **Emotive Display:** Features a 128x64 OLED screen acting as a reactive face that syncs with movement.
*   **Fully Printable:** Designed entirely for 3D printing in PLA with minimal supports.
*   **Network Connectivity:** Connect to your WiFi network for remote control and API access.
*   **JSON API:** RESTful API for programmatic control from Python, JavaScript, and more.
*   **Conversational Faces:** Expressive emotion library with talk variants for voice assistant projects.
*   **Sesame Studio:** New animation composer software to easily create custom movements.
*   **Sesame Companion App:** Python application for voice control and advanced interactions.
*   **Serial CLI:** Control the robot and trigger animations via a Serial Command Line Interface or the web UI.
*   **Pre-programmed Emotes:** Includes animations for Walking, Waving, Dancing, Pointing, Resting, and more.


## Watch the launch video on YouTube

<a href="https://www.youtube.com/watch?v=1UDsWkcQZhc"><img src="https://github.com/user-attachments/assets/710cb5a6-163e-47e7-a294-5e2d2ab07627" width="70%" alt="thumb-youtube"></a>

___

## Getting Started

Follow these steps to build your own Sesame Robot:

### 1. Gather Parts 
Check the **[Bill of Materials (BOM)](hardware/bom/README.md)** for a complete list of required electronics and hardware.
*   **Microcontroller (this fork):** [Waveshare ESP32-S3-Zero-M](https://www.amazon.ca/dp/B0G43ZYD8G) (~$13.30 CAD each in a 3-pack) — pre-soldered headers guaranteed in the listing, dual-core ESP32-S3, USB-C. (Upstream alternatives: Lolin S2 Mini, Sesame Distro Board V3, or ESP32-DevKitC-32E + Distro Board V1 — all still supported by this fork's firmware.)
*   **Servo Wiring (this fork, recommended if soldering the 3×8 header block sounds miserable):** A [PCA9685 16-Channel PWM Servo Driver board](https://www.amazon.ca/PCA9685-Interface-Controller-Compatible-Raspberry/dp/B07RMTN4NZ) (~$14 CAD) replaces the hand-wired header array. Servos plug directly into it; only 4 wires connect it to the S3 Mini (VCC, GND, SDA, SCL). See [`docs/pca9685-fork/README.md`](docs/pca9685-fork/README.md).
*   Actuators: 8x MG90 Servos
*   Power: 5V 3A source (USB-C PD for S2 Mini and V2 Distro Board, or battery + buck converter; see BOM for the Bambu Lab 14500 7.4V 800mAh Li-ion Battery option)

### 2. Print Parts 
Download the STLs and follow the **[Printing Guide](hardware/printing/README.md)**.
*   Designed for PLA
*   Minimal supports required
*   **This fork adds an optional "sunroof" top cover** ([`Top-Cover-Enclosed-v117-PCA9685-sunroof.stl`](hardware/printing/stl/top-covers/)) with a cutout for PCA9685 connector/wire access — see [`docs/pca9685-fork/README.md`](docs/pca9685-fork/README.md#3d-printing-the-sunroof-top-cover). The stock top cover works fine too if you'd rather keep it fully enclosed.

### 3. Build & Wire 
Follow the **[Build Guide](docs/build-guide/README.md)** and **[Wiring Guide](docs/wiring-guide/README.md)** to assemble the frame and connect the electronics.

### 4. Flash Firmware 
Upload the code from the **[Firmware Directory](firmware/README.md)**.
*   Requires Arduino IDE
*   Configure WiFi AP settings

### 5. Create Animations 
Use **[Sesame Studio](software/sesame-studio/README.md)** to visually design poses and sequences for your robot.

<img width="100%" height="728" alt="sesame-wakeup-gif" src="https://github.com/user-attachments/assets/a4951195-4253-40a4-a87d-d14fad57ff5f" />

---

## Software & Firmware

### Sesame Studio
Sesame Studio is a standalone desktop application included in `software/sesame-studio/`. It allows you to:
*   Visually pose the robot using a schematic interface.
*   Generate C++ code for servo angles automatically.
*   Sequence frames into complex animations.

[**> Go to Sesame Studio**](software/sesame-studio/README.md)


### Sesame Simulator
The Sesame Simulator, created by Jay Li, is a Rust-based 3D simulation environment for testing Sesame's movements and kinematics in a virtual space. It features:
*   **Physics-based Simulation:** Test walking and balance without hardware.
*   **Web-based Interface:** Run the simulator directly in your browser.
*   **URDF Integration:** Accurate modeling of Sesame's physical properties.

[**> Go to Sesame Simulator**](https://one-for-all.github.io/sesame-robot-sim/)

### Sesame Companion App
The Sesame Companion App is a Python-based application that enables advanced control and interaction with your robot over your local network. It leverages the new JSON API and network mode features to provide:
*   **Voice Assistant Integration:** Control Sesame with voice commands and see real-time emotional expressions.
*   **Remote Control:** Command your robot from anywhere on your local network.
*   **Face Control:** Change expressions dynamically based on conversation or context.
*   **API Examples:** Reference implementation for building your own integrations.

The Companion App works with robots running the latest firmware with network mode enabled.

[**> Go to Sesame Companion App Repository**](https://github.com/dorianborian/sesame-companion-app)

### Firmware
The ESP32 firmware (`sesame-firmware-main.ino`) handles the kinematics, face display, and WiFi control interface.
*   **Web UI:** Control the robot from your phone via the built-in Access Point.
*   **Custom Faces:** Add your own bitmaps (guide in firmware docs).

[**> Go to Firmware Docs**](firmware/README.md)


---

## Contributing

This robot is a platform for building new features, cosmetics, tools, and ideas. Since the current firmware is a basic implementation, pull requests are very welcome for:
*   Kinematics improvements
*   New animations
*   Improved Web UI/UX
*   Sensor integration (Ultrasonic, Gyro, etc.)

I would also love to see forks of this project with new hardware, software, faces, etc. Be sure to send me a message if you end up building one, and I might feature you on my website or channel!
  
---

*Created by [Dorian Todd](https://www.doriantodd.com/). Need help with your Sesame Robot? Send me a message on Discord, my username is "starphee"*

*This PCA9685 fork is maintained by [YOUR NAME / GITHUB HANDLE HERE]. Please file issues on this fork's tracker for anything specific to the PCA9685 wiring/firmware changes, and use the [upstream repo](https://github.com/dorianborian/sesame-robot) for everything else.*
