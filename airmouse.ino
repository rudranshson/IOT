#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>

// --- NETWORK CONFIGURATION ---
const char* ssid = "";
const char* password = "";
const char* targetIP = ""; // Updated to your new local IP
const int udpPort = 4210;

// --- HARDWARE CONFIGURATION ---
const int MPU_ADDR = 0x68; // I2C address of the MPU-6050
const int FLASH_BTN = 0;   // GPIO0 is the NodeMCU's built-in Flash button

WiFiUDP udp;
int16_t gyroX, gyroY, gyroZ;
int gx, gy, btnState;

void setup() {
  // 1. Initialize the Flash Button
  pinMode(FLASH_BTN, INPUT_PULLUP);

  // 2. Initialize I2C and overclock the bus to 400kHz for zero-latency reads
  Wire.begin();
  Wire.setClock(400000); 
  
  // 3. Wake up the MPU-6050
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B); // PWR_MGMT_1 register
  Wire.write(0);    // Write 0 to wake up
  Wire.endTransmission(true);

  // 4. Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); // Wait silently for connection
  }
  
  // 5. Start the UDP connection
  udp.begin(udpPort);
}

void loop() {
  // Request Gyroscope data
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x43); // Start reading at the GYRO_XOUT_H register
  Wire.endTransmission(false);
  
  // Safely request 6 bytes 
  Wire.requestFrom((uint8_t)MPU_ADDR, (size_t)6); 
  
  // Only read if the data is fully available to prevent corrupted packets
  if (Wire.available() == 6) {
    gyroX = Wire.read() << 8 | Wire.read();
    gyroY = Wire.read() << 8 | Wire.read();
    gyroZ = Wire.read() << 8 | Wire.read();
  }

  // Scale the raw data down to match the Python script's sensitivity expectations
  gx = -gyroY / 150; 
  gy = gyroX / 150; 

  // Read the Flash button (Pressed = LOW due to the internal pull-up resistor)
  if (digitalRead(FLASH_BTN) == LOW) {
    btnState = 1;
  } else {
    btnState = 0;
  }

  // Build the comma-separated packet exactly as Python expects
  String packet = String(gx) + "," + String(gy) + "," + String(btnState);
  
  // Blast the data over Wi-Fi to the laptop
  udp.beginPacket(targetIP, udpPort);
  udp.write(packet.c_str());
  udp.endPacket();

  // A 20ms delay creates a perfect 50Hz polling rate.
  delay(20); 
}