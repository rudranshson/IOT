import socket
import time
import sys
from evdev import UInput, ecodes as e

UDP_IP = "0.0.0.0" 
UDP_PORT = 4210    

cap = {
    e.EV_REL: (e.REL_X, e.REL_Y, e.REL_WHEEL),
    e.EV_KEY: (e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE),
}

try:
    ui = UInput(cap, name='wifi_air_mouse')
except Exception as err:
    print("Error: You must run this script with sudo.")
    sys.exit(1)

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Wi-Fi Air Mouse Server listening on port {UDP_PORT}...")
except Exception as err:
    print(f"Failed to bind UDP socket: {err}")
    sys.exit(1)

# --- DPI PROFILES ---
dpi_profiles = [
    (0.15, 0.015),  # Profile 0: Precision (Slow)
    (0.25, 0.025),  # Profile 1: Normal (Medium)
    (0.45, 0.04)    # Profile 2: Fast (High)
]
dpi_names = ["Precision (Slow)", "Normal (Medium)", "Fast (High)"]

current_dpi_state = 1
base_sensitivity, acceleration = dpi_profiles[current_dpi_state]

smoothing = 0.45              
micro_deadzone = 2           
prev_x, prev_y = 0.0, 0.0

# --- BUTTON LOGIC VARIABLES ---
CLICK_TIMEOUT = 0.35 
HOLD_TIMEOUT = 0.25      
flash_press_count = 0
last_press_time, button_down_time = 0, 0
flash_released = True
is_dragging = False 
is_scrolling = False

print(f"[*] Started in {dpi_names[current_dpi_state]} mode.")
print("Advanced Wi-Fi Air Mouse Active. Press Ctrl+C to stop.")

while True:
    try:
        data, addr = sock.recvfrom(1024) 
        line = data.decode('utf-8').strip()
        if not line: continue
            
        parts = line.split(',')
        if len(parts) == 4: 
            gx, gy = int(parts[0]), int(parts[1])
            flash_btn = int(parts[2])
            incoming_dpi = int(parts[3])
            
            # --- PORT SHIFTING LOGIC ---
            if incoming_dpi != current_dpi_state:
                current_dpi_state = incoming_dpi
                base_sensitivity, acceleration = dpi_profiles[current_dpi_state]
                print(f"[+] Hardware Wire Moved -> DPI set to: {dpi_names[current_dpi_state]}")
            
            # Apply Deadzone & Smoothing
            if abs(gx) <= micro_deadzone: gx = 0
            if abs(gy) <= micro_deadzone: gy = 0
            
            curr_x = (gx * smoothing) + (prev_x * (1.0 - smoothing))
            curr_y = (gy * smoothing) + (prev_y * (1.0 - smoothing))
            prev_x, prev_y = curr_x, curr_y
            
            # Apply Dynamic Acceleration
            speed_multiplier_x = 1.0 + (abs(curr_x) * acceleration)
            speed_multiplier_y = 1.0 + (abs(curr_y) * acceleration)
            
            dx = int(curr_x * base_sensitivity * speed_multiplier_x)
            dy = int(curr_y * base_sensitivity * speed_multiplier_y)
            
            # --- SMART GESTURE LOGIC (Clicks, Drag, Scroll) ---
            if flash_btn == 1 and flash_released:
                flash_released = False
                button_down_time = time.time()
            elif flash_btn == 1 and not flash_released:
                if not is_dragging and not is_scrolling and (time.time() - button_down_time > HOLD_TIMEOUT):
                    if flash_press_count == 0:
                        is_dragging = True
                        ui.write(e.EV_KEY, e.BTN_LEFT, 1) 
                        ui.syn()
                    elif flash_press_count >= 1:
                        is_scrolling = True
                        flash_press_count = 0 
            elif flash_btn == 0 and not flash_released:
                flash_released = True
                if is_dragging:
                    is_dragging = False 
                    ui.write(e.EV_KEY, e.BTN_LEFT, 0) 
                    ui.syn()
                elif is_scrolling:
                    is_scrolling = False
                else:
                    flash_press_count += 1
                    last_press_time = time.time()

            if is_scrolling:
                if dy != 0:
                    ui.write(e.EV_REL, e.REL_WHEEL, int(-dy * 0.1)) 
                    ui.syn()
            else:
                if dx != 0 or dy != 0:
                    ui.write(e.EV_REL, e.REL_X, dx)
                    ui.write(e.EV_REL, e.REL_Y, dy)
                    ui.syn() 

        if flash_press_count > 0 and flash_released and not is_dragging and not is_scrolling and (time.time() - last_press_time > CLICK_TIMEOUT):
            if flash_press_count == 1:
                ui.write(e.EV_KEY, e.BTN_LEFT, 1); ui.syn(); time.sleep(0.02)
                ui.write(e.EV_KEY, e.BTN_LEFT, 0); ui.syn()
            elif flash_press_count == 2:
                ui.write(e.EV_KEY, e.BTN_LEFT, 1); ui.syn(); time.sleep(0.02)
                ui.write(e.EV_KEY, e.BTN_LEFT, 0); ui.syn(); time.sleep(0.05)
                ui.write(e.EV_KEY, e.BTN_LEFT, 1); ui.syn(); time.sleep(0.02)
                ui.write(e.EV_KEY, e.BTN_LEFT, 0); ui.syn()
            elif flash_press_count >= 3:
                ui.write(e.EV_KEY, e.BTN_RIGHT, 1); ui.syn(); time.sleep(0.02)
                ui.write(e.EV_KEY, e.BTN_RIGHT, 0); ui.syn()
            flash_press_count = 0

    except ValueError: 
        pass 
    except KeyboardInterrupt:
        print("\nExiting Wi-Fi Air Mouse...")
        sock.close()
        ui.close()
        break
