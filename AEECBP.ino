// ===== BMW M5 (F90 Competition) Robust Cluster Simulator - Arduino Uno =====
// A0 = Potentiometer (Throttle Pedal)
// Features:
//  - Burst outlier rejection (ignores floating/glitch spikes)
//  - Endpoint snap deadzones (clean 0% idle & solid 100% full turn)
//  - Checksum-verified EEPROM calibration (CAL_START / CAL_SAVE / CAL_RESET / POT_INVERT)
//  - Direct responsive speed, gear (1..8), and RPM mapping

#include <EEPROM.h>
#include <math.h>

#define HUMAN_READABLE  0     // 0 = Key:Value telemetry (dashboard + Plotter), 1 = Serial Monitor text

// ---------- Pin & Sampling Settings ----------
const byte  POT_PIN = A0;

const int   SAMPLES = 16;
const int   TRIM    = 4;
const int   POT_SPREAD_MAX = 220;             // Reject burst if A0 floats/glitches > 220 counts in 3ms
const unsigned long SAMPLE_INTERVAL_MS = 20;  // 50 Hz physics & ADC update
const unsigned long PRINT_INTERVAL_MS  = 80;  // 12.5 Hz serial output

// ---------- EEPROM Calibration ----------
const uint16_t CAL_MAGIC = 0xAE54;
struct CalData {
  uint16_t magic;
  float    adcMin;
  float    adcMax;
  uint8_t  potInvert;     // 0 = normal (low->high), 1 = inverted (high->low)
  uint16_t checksum;
};

float adcMin    = 6.0f;
float adcMax    = 1017.0f;
bool  potInvert = false;

bool  calibrating = false;
float calMin      = 1023.0f;
float calMax      = 0.0f;

// ---------- Cluster & Gear Table ----------
const float IDLE_RPM      = 650.0f;
const float REDLINE_RPM   = 7200.0f;
const float MAX_SPEED_KMH = 220.0f;

const float UP_KMH[7]       = {35.0f, 62.0f, 90.0f, 120.0f, 150.0f, 180.0f, 205.0f};
const float DOWN_KMH[7]     = {30.0f, 56.0f, 84.0f, 113.0f, 143.0f, 173.0f, 198.0f};
const float GEAR_MIN_KMH[8] = {0.0f,   30.0f,  56.0f,  84.0f,  113.0f, 143.0f, 173.0f, 198.0f};
const float GEAR_MAX_KMH[8] = {35.0f,  62.0f,  90.0f,  120.0f, 150.0f, 180.0f, 205.0f, 220.0f};
const float GEAR_MIN_RPM[8] = {650.0f, 3300.0f, 3700.0f, 4100.0f, 4400.0f, 4700.0f, 5100.0f, 5500.0f};
const float GEAR_MAX_RPM[8] = {5800.0f, 6000.0f, 6200.0f, 6400.0f, 6600.0f, 6800.0f, 6950.0f, 7100.0f};

// ---------- State ----------
float filtered = 0.0f;
float rpm      = IDLE_RPM;
float speedKmh = 0.0f;
float throttle = 0.0f;        // 0..1
int   gear     = 0;           // 0..7 (displayed as 1..8)
unsigned long lastSample = 0, lastPrint = 0;

String cmdBuf = "";

// ---------- Calibration & ADC Helpers ----------
uint16_t computeChecksum(const CalData &c) {
  uint32_t h = c.magic;
  h = h * 31u + (uint32_t)roundf(c.adcMin * 10.0f);
  h = h * 31u + (uint32_t)roundf(c.adcMax * 10.0f);
  h = h * 31u + c.potInvert;
  return (uint16_t)(h ^ (h >> 16));
}

void loadCalibration() {
  CalData cal;
  EEPROM.get(0, cal);
  if (cal.magic == CAL_MAGIC &&
      cal.checksum == computeChecksum(cal) &&
      !isnan(cal.adcMin) && !isnan(cal.adcMax) &&
      cal.adcMin >= 0.0f && cal.adcMax <= 1023.0f &&
      (cal.adcMax - cal.adcMin) >= 15.0f) {
    adcMin    = cal.adcMin;
    adcMax    = cal.adcMax;
    potInvert = (cal.potInvert == 1);
  }
}

void saveCalibration() {
  CalData cal;
  cal.magic     = CAL_MAGIC;
  cal.adcMin    = adcMin;
  cal.adcMax    = adcMax;
  cal.potInvert = potInvert ? 1 : 0;
  cal.checksum  = computeChecksum(cal);
  EEPROM.put(0, cal);
}

bool readPotClean(float &outVal) {
  analogRead(POT_PIN);
  int s[SAMPLES];
  for (int i = 0; i < SAMPLES; i++) {
    s[i] = analogRead(POT_PIN);
    delayMicroseconds(180);
  }
  for (int i = 1; i < SAMPLES; i++) {
    int key = s[i], j = i - 1;
    while (j >= 0 && s[j] > key) { s[j + 1] = s[j]; j--; }
    s[j + 1] = key;
  }
  int spread = s[SAMPLES - 1 - TRIM] - s[TRIM];
  if (spread > POT_SPREAD_MAX) {
    return false;
  }
  long sum = 0;
  for (int i = TRIM; i < SAMPLES - TRIM; i++) sum += s[i];
  outVal = (float)sum / (SAMPLES - 2 * TRIM);
  return true;
}

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd == "CAL_START") {
    calibrating = true;
    calMin = filtered;
    calMax = filtered;
  } else if (cmd == "CAL_SAVE") {
    if (calibrating && (calMax - calMin) >= 15.0f) {
      float span = calMax - calMin;
      float pad  = max(1.5f, span * 0.025f);
      float nMin = calMin + pad;
      float nMax = calMax - pad;
      if (nMax - nMin < 8.0f) {
        nMin = calMin;
        nMax = calMax;
      }
      adcMin = nMin;
      adcMax = nMax;
      saveCalibration();
    }
    calibrating = false;
  } else if (cmd == "CAL_CANCEL") {
    calibrating = false;
  } else if (cmd == "CAL_RESET") {
    calibrating = false;
    adcMin    = 6.0f;
    adcMax    = 1017.0f;
    potInvert = false;
    saveCalibration();
  } else if (cmd == "POT_INVERT") {
    potInvert = !potInvert;
    saveCalibration();
  }
}

void pollSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdBuf.length() > 0) {
        handleCommand(cmdBuf);
        cmdBuf = "";
      }
    } else if (cmdBuf.length() < 32) {
      cmdBuf += c;
    }
  }
}

void updateThrottle() {
  float raw = filtered;
  if (!readPotClean(raw)) {
    return; // Ignore noisy/floating burst
  }

  float diff = raw - filtered;
  float adiff = fabs(diff);
  if (adiff > 1.5f) {
    float alpha = (adiff > 25.0f) ? 0.60f : 0.32f;
    filtered += alpha * diff;
  }

  if (calibrating) {
    if (filtered < calMin) calMin = filtered;
    if (filtered > calMax) calMax = filtered;
  }

  float span = adcMax - adcMin;
  if (span < 15.0f) span = 15.0f;
  float x = (filtered - adcMin) / span;
  x = constrain(x, 0.0f, 1.0f);
  if (potInvert) x = 1.0f - x;

  // Endpoint snap deadzones for rock-steady 0% idle and solid 100% full turn
  if (x <= 0.02f) x = 0.0f;
  else if (x >= 0.985f) x = 1.0f;
  else x = (x - 0.02f) / 0.965f;

  throttle = constrain(x, 0.0f, 1.0f);
}

void updateGaugesDirect(float dt) {
  float targetSpeed = (throttle <= 0.005f) ? 0.0f : (throttle * MAX_SPEED_KMH);

  // Follow knob rapidly and stop completely once knob stops turning
  float alphaSpd = 1.0f - expf(-10.0f * dt);
  speedKmh += (targetSpeed - speedKmh) * alphaSpd;
  if (fabs(targetSpeed - speedKmh) < 0.25f) speedKmh = targetSpeed;
  if (targetSpeed == 0.0f && speedKmh < 0.3f) speedKmh = 0.0f;

  while (gear < 7 && speedKmh >= UP_KMH[gear]) gear++;
  while (gear > 0 && speedKmh < DOWN_KMH[gear - 1]) gear--;

  float frac = (speedKmh - GEAR_MIN_KMH[gear]) / (GEAR_MAX_KMH[gear] - GEAR_MIN_KMH[gear]);
  frac = constrain(frac, 0.0f, 1.0f);
  float targetRpm = GEAR_MIN_RPM[gear] + frac * (GEAR_MAX_RPM[gear] - GEAR_MIN_RPM[gear]);

  float alphaRpm = 1.0f - expf(-14.0f * dt);
  rpm += (targetRpm - rpm) * alphaRpm;
  if (fabs(targetRpm - rpm) < 5.0f) rpm = targetRpm;
}

void setup() {
  Serial.begin(115200);
  loadCalibration();
  float initVal = 0.0f;
  if (readPotClean(initVal)) filtered = initVal;
  else filtered = (float)analogRead(POT_PIN);
  lastSample = millis();
}

void loop() {
  pollSerialCommands();
  unsigned long now = millis();

  if (now - lastSample >= SAMPLE_INTERVAL_MS) {
    float dt = (now - lastSample) / 1000.0f;
    if (dt > 0.05f) dt = 0.05f;
    lastSample = now;
    updateThrottle();
    updateGaugesDirect(dt);
  }

  if (now - lastPrint >= PRINT_INTERVAL_MS) {
    lastPrint = now;
    int rpmOut   = ((int)(rpm / 10.0f + 0.5f)) * 10;
    int speedOut = (int)(speedKmh + 0.5f);
    int thrPct   = (int)(throttle * 100.0f + 0.5f);
    int outMin   = (int)(calibrating ? calMin : adcMin);
    int outMax   = (int)(calibrating ? calMax : adcMax);

#if HUMAN_READABLE
    Serial.print(F("BMW M5 | Gear: ")); Serial.print(gear + 1);
    Serial.print(F(" | RPM: "));        Serial.print(rpmOut);
    Serial.print(F(" | Speed: "));      Serial.print(speedOut);
    Serial.print(F(" km/h | Thr: "));   Serial.print(thrPct);
    Serial.print(F("% | Raw: "));       Serial.println((int)filtered);
#else
    Serial.print("RPM:");        Serial.print(rpmOut);
    Serial.print(",Speed_x20:"); Serial.print(speedOut * 20);
    Serial.print(",Gear_x500:"); Serial.print((gear + 1) * 500);
    Serial.print(",Throttle:");  Serial.print(thrPct);
    Serial.print(",Inv:");       Serial.print(potInvert ? 1 : 0);
    Serial.print(",Raw:");       Serial.print((int)filtered);
    Serial.print(",Cal:");       Serial.print(calibrating ? 1 : 0);
    Serial.print(",AdcMin:");    Serial.print(outMin);
    Serial.print(",AdcMax:");    Serial.print(outMax);
    Serial.print(",Redline:");   Serial.println((int)REDLINE_RPM);
#endif
  }
}
