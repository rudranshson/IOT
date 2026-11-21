# Wi-Fi Air Mouse (Router / Mobile Hotspot LAN Edition)

![Platform](https://img.shields.io/badge/MCU-NodeMCU%20Amica%20(ESP8266)-blue)
![Sensor](https://img.shields.io/badge/Sensor-MPU--6050%20IMU-orange)
![Host OS](https://img.shields.io/badge/Host-Ubuntu%20Linux%20(evdev)-E95420)
![Protocol](https://img.shields.io/badge/Protocol-UDP%20Port%204210-green)
![Language](https://img.shields.io/badge/Stack-C%2B%2B%20%7C%20Python%203-informational)

A low-latency, surface-independent wireless air mouse built with a **NodeMCU Amica (ESP8266)** and an **MPU-6050 6-axis IMU**. Both the microcontroller and host PC connect over an existing Wi-Fi router or mobile hotspot (Station Mode) to stream real-time angular velocity, button states, and hardware DPI settings over **UDP (Port 4210)** into a Linux kernel-level virtual mouse via `evdev`.

All packet traffic remains strictly inside the local subnet—zero internet bandwidth or mobile data is consumed while running.

---

## System Architecture

```text
+-------------------+    I2C (400 kHz)     +---------------------------+
|   MPU-6050 IMU    | -------------------> |  NodeMCU Amica (ESP8266)  |
|  3-Axis Gyroscope |   SDA: D2, SCL: D1   |  + Onboard Flash Btn (D3) |
+-------------------+                      |  + Hardware DPI (D5-D7)   |
                                           +-------------+-------------+
                                                         |
                                              Wi-Fi STA (UDP :4210)
                                                         v
                                           +---------------------------+
                                           | Router / Mobile Hotspot   |
                                           | (Local LAN & DHCP Bridge) |
                                           +-------------+-------------+
                                                         |
                                               Local Subnet Delivery
                                                         v
                                           +---------------------------+
                                           |  Ubuntu Linux Host        |
                                           |  airmouse.py -> evdev     |
                                           |  (/dev/uinput HID Mouse)  |
                                           +---------------------------+
```

---

## Key Features

* **Low-Latency UDP Telemetry:** Streams compact comma-separated packets (`gx,gy,btn,dpi`) over UDP port `4210` with ESP8266 Wi-Fi sleep disabled (`WIFI_NONE_SLEEP`) and fixed-buffer `snprintf` formatting to prevent heap fragmentation.
* **On-Chip Hardware Filtering & Auto-Calibration:** Enables the MPU-6050 internal Digital Low-Pass Filter (register `0x1A` set to `0x03` for 42 Hz gyroscope bandwidth) and runs a 250-sample zero-rate bias calibration on startup.
* **Physical 3-Gear Hardware DPI Switch:** A single Ground jumper wire acts as a tactile sensitivity selector across pins `D5` (Precision), `D6` (Normal), and `D7` (Fast) using internal pull-up resistors (`INPUT_PULLUP`).
* **Single-Button Smart Gesture Engine:** A time-based Finite State Machine (FSM) maps the NodeMCU's built-in `FLASH` button (`GPIO0`) to five actions: left click, double click, right click, drag/multi-file selection, and vertical scrolling.
* **Signal-Processing Pipeline:** Combines deadzone noise rejection, Exponential Moving Average (EMA) smoothing, non-linear dynamic acceleration, sub-pixel remainder tracking, and non-blocking UDP burst draining.
* **Kernel-Level Linux HID Input:** Injects relative pointer and button events directly into `/dev/uinput` via Python `evdev`, working natively across desktop environments, terminals, browsers, and code editors.

---

## Hardware Requirements

* **Microcontroller:** NodeMCU Amica (ESP8266)
* **Motion Sensor:** MPU-6050 (6-axis Gyroscope + Accelerometer breakout)
* **Prototyping:** Breadboard and male-to-male / male-to-female jumper wires
* **Power:** Micro-USB cable (laptop USB port or 5V power bank)
* **Network Bridge:** Standard 2.4 GHz Wi-Fi router or smartphone mobile hotspot
* **Host Machine:** Linux PC with Python 3 (tested on Ubuntu Linux)

---

## Circuit Wiring & Pinout

### MPU-6050 to NodeMCU Amica (I2C Bus)

| MPU-6050 Pin | NodeMCU Pin | GPIO | Function |
| :--- | :--- | :--- | :--- |
| **VCC** | `3V3` | — | 3.3V sensor power supply |
| **GND** | `GND` | — | Common ground reference |
| **SCL** | `D1` | `GPIO5` | I2C Serial Clock |
| **SDA** | `D2` | `GPIO4` | I2C Serial Data |

### Hardware Controls

| Control | NodeMCU Pin | Wiring / Trigger | Behavior |
| :--- | :--- | :--- | :--- |
| **Action Button** | `D3` (`GPIO0`) | Onboard `FLASH` button | Active `LOW` (`INPUT_PULLUP`) for clicks, drag, and scroll |
| **DPI: Precision (Slow)** | `D5` (`GPIO14`) | Connect jumper from `GND` to `D5` | Low sensitivity for pinpoint clicking |
| **DPI: Normal (Medium)** | `D6` (`GPIO12`) | Connect jumper from `GND` to `D6` (or leave floating) | Balanced daily navigation (default) |
| **DPI: Fast (High)** | `D7` (`GPIO13`) | Connect jumper from `GND` to `D7` | Rapid full-screen sweeps |

> **Note:** Pins `D3` and `D4` are involved in the ESP8266 boot sequence—keep the hardware DPI wire restricted to `D5`, `D6`, and `D7`.

---

## Single-Button Gesture Controls

| Physical Action (`FLASH` Button) | Resulting OS Event |
| :--- | :--- |
| **Single Tap** | Left Click |
| **Double Tap** | Double Click |
| **Triple Tap** | Right Click |
| **Press & Hold (> 0.25s) + Tilt** | Drag / Draw Multi-File Selection Box |
| **Tap, then Press & Hold + Tilt Up/Down** | Vertical Scroll Wheel |

---

## Signal Processing & Packet Format

### UDP Packet Structure
Every ~12–15 ms, the ESP8266 transmits an ASCII payload over UDP port `4210`:

```text
gx,gy,btn,dpi
```
* `gx`: Horizontal delta derived from `-(gyroY - offsetY) / 50` (side-to-side wrist tilt)
* `gy`: Vertical delta derived from `(gyroX - offsetX) / 50` (up-and-down pitch)
* `btn`: `1` when `FLASH` is pressed, `0` when released
* `dpi`: `0` (`D5` Precision), `1` (`D6`/Default Normal), or `2` (`D7` Fast)

### Host Filtering Pipeline (`airmouse.py`)
1. **Micro-Deadzone:** Forces raw deltas within $\pm 6$ to `0` to suppress resting hand tremor and residual thermal drift.
2. **Exponential Moving Average (EMA):** Smooths jitter across consecutive frames:
   $$\text{curr} = (\alpha \cdot g) + \big((1 - \alpha) \cdot \text{prev}\big)$$
3. **Non-Linear Dynamic Acceleration:** Preserves fine control during slow tilts while accelerating fast wrist flicks:
   $$\Delta x = \text{curr}_x \cdot s_{\text{base}} \cdot \big(1 + \vert{}\text{curr}_x\vert{} \cdot a\big)$$
4. **Sub-Pixel Accumulator:** Retains fractional pixel remainders across frames so slow diagonal motion stays fluid instead of snapping in coarse steps.

---

## Setup & Installation

### 1. Connect Both Devices to the Same Network
Connect your Ubuntu machine to your Wi-Fi router or 2.4 GHz mobile hotspot, then find its local IPv4 address:

```bash
ip a
```

Locate your wireless interface (for example, `wlp3s0` or `wlan0`) and note its `inet` IPv4 address (e.g., `192.168.43.100`).

### 2. Flash the NodeMCU Amica (Arduino IDE)
1. Install the **ESP8266 Community** board package in Arduino IDE and select **NodeMCU 1.0 (ESP-12E Module)**.
2. Open the firmware sketch (`firmware/airmouse_sta.ino`) and update your network settings at the top of the file:
   ```cpp
   const char* ssid = "MyHotspotSSID";
   const char* password = "MyHotspotPassword";
   const char* targetIP = "192.168.43.100"; // Replace with your Linux host IP from `ip a`
   const int udpPort = 4210;
   ```
3. Upload the sketch to the NodeMCU.
4. **Important:** Leave the breadboard flat and completely still for **2 seconds** immediately after upload or reset so the MPU-6050 finishes auto-calibration.

### 3. Configure the Ubuntu Linux Host
Create a Python virtual environment and install `evdev`:

```bash
python3 -m venv airmouse_env
airmouse_env/bin/pip install evdev
```

Disable Linux Wi-Fi power saving on your wireless interface to prevent packet batching and cursor stutter:

```bash
sudo iw dev wlp3s0 set power_save off
```

### 4. Run the Receiver
Start the host driver with `sudo` (required for `/dev/uinput` kernel access):

```bash
sudo airmouse_env/bin/python airmouse.py
```

Move the Ground jumper wire between `D5`, `D6`, and `D7`—the terminal logs each live DPI transition immediately. Press `Ctrl+C` to stop the driver.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
| :--- | :--- | :--- |
| **No cursor movement** | DHCP leased a new IP to your laptop after reconnecting | Run `ip a`, update `targetIP` in the `.ino` sketch, and re-upload (or assign a static DHCP lease on your router). |
| **Cursor drifts while still** | Board moved during startup calibration or sensor warmed up | Set the breadboard flat on a desk and press the NodeMCU `RST` button for 2 seconds to re-zero offsets. |
| **Periodic stutters or lag** | Host Wi-Fi power saving or mobile hotspot sleep throttling | Run `sudo iw dev wlp3s0 set power_save off`, keep the phone hotspot unlocked/unthrottled, and verify `wlp3s0` signal quality. |
| **`PermissionError` on startup** | Missing `/dev/uinput` write permission | Launch the script with `sudo` (or add a `udev` rule granting your user access to `/dev/uinput`). |

---

## Roadmap & Future Improvements

* **ESP32 + BLE HID Migration:** Replace the ESP8266 with an ESP32 to expose a native Bluetooth Low Energy mouse—removing the need for a host Python script, `sudo`, and Wi-Fi router overhead while cutting power draw.
* **6-Axis Sensor Fusion:** Combine accelerometer and gyroscope data via a Complementary or Kalman filter for tilt-compensated cursor leveling.
* **Custom Enclosure & Battery Power:** Transition from breadboard to a soldered perfboard/PCB powered by a 3.7V Li-Po battery with a TP4056 charger, a 3-position physical DPI slide switch, and a 3D-printed ergonomic shell.

---

## Author

**Rudransh Sonke**  
B.Tech Computer Science & Engineering — MIT ADT University, Pune
