// ===== BMW M5 (F90 Competition) Robust Simulator - Arduino Uno =====
// A0 = Potentiometer (Throttle Pedal) with burst outlier rejection, EEPROM CRC calibration & invert support
// D2 = 3-Pin IR Obstacle / Reflective Sensor (with debounce + toggleable active-LOW/HIGH polarity):
//      - Engine OFF + Wave/Cover IR           -> Starter Cranks & Fires Up V8
//      - Parked + Idle + Hold IR >= 1.2s      -> Engine Shutoff
//      - Stopped + Cover IR + Throttle >= 18% -> Launch Control (3500 RPM 2-step); Release IR to Launch!
//      - Moving + Cover IR                    -> Touchless Brake Pedal

#include <EEPROM.h>
#include <math.h>

#define HUMAN_READABLE  0     // 0 = Key:Value telemetry (dashboard + Plotter), 1 = Serial Monitor text

// ---------- Pin & Sampling Settings ----------
const byte  POT_PIN = A0;
const byte  IR_PIN  = 2;                  // D2 digital input (INPUT_PULLUP)

const int   SAMPLES = 16;
const int   TRIM    = 4;
const int   POT_SPREAD_MAX = 220;         // Reject burst if A0 floats/glitches > 220 counts in 3ms
const unsigned long SAMPLE_INTERVAL_MS = 20;    // 50 Hz physics & ADC update
const unsigned long PRINT_INTERVAL_MS  = 90;    // ~11 Hz serial output

// ---------- EEPROM Calibration ----------
const uint16_t CAL_MAGIC = 0xAE53;
struct CalData {
  uint16_t magic;
  float    adcMin;
  float    adcMax;
  uint8_t  potInvert;     // 0 = normal (low->high), 1 = inverted (high->low)
  uint8_t  irActiveLow;   // 1 = LOW when covered (FC-51/TCRT5000), 0 = HIGH when covered
  uint16_t checksum;
};

float   adcMin      = 6.0f;
float   adcMax      = 1017.0f;
bool    potInvert   = false;
bool    irActiveLow = true;

bool    calibrating = false;
float   calMin      = 1023.0f;
float   calMax      = 0.0f;

// ---------- Cluster & Gear Table ----------
const float IDLE_RPM       = 650.0f;
const float LAUNCH_RPM     = 3500.0f;
const float REDLINE_RPM    = 7200.0f;
const float MAX_SPEED_KMH  = 220.0f;
const unsigned long CRANK_TIME_MS   = 950;
const unsigned long FLARE_TIME_MS   = 750;
const unsigned long SHUTOFF_HOLD_MS = 1200;

const float UP_KMH[7]       = {35.0f, 62.0f, 90.0f, 120.0f, 150.0f, 180.0f, 205.0f};
const float DOWN_KMH[7]     = {30.0f, 56.0f, 84.0f, 113.0f, 143.0f, 173.0f, 198.0f};
const float GEAR_MIN_KMH[8] = {0.0f,   30.0f,  56.0f,  84.0f,  113.0f, 143.0f, 173.0f, 198.0f};
const float GEAR_MAX_KMH[8] = {35.0f,  62.0f,  90.0f,  120.0f, 150.0f, 180.0f, 205.0f, 220.0f};
const float GEAR_MIN_RPM[8] = {650.0f, 3300.0f, 3700.0f, 4100.0f, 4400.0f, 4700.0f, 5100.0f, 5500.0f};
const float GEAR_MAX_RPM[8] = {5800.0f, 6000.0f, 6200.0f, 6400.0f, 6600.0f, 6800.0f, 6950.0f, 7100.0f};

// ---------- Engine & Input State ----------
enum EngState { ENG_OFF = 0, ENG_CRANKING = 1, ENG_RUNNING = 2 };
EngState engState = ENG_OFF;

float filtered = 0.0f;
float rpm      = 0.0f;
float speedKmh = 0.0f;
float throttle = 0.0f;        // 0..1
int   gear     = 0;           // 0..7 (displayed as 1..8)

bool  irDetected = false;
bool  irRawPrev  = false;
unsigned long irChangeMs = 0;
bool  irHoldEligibleShutoff = false;
unsigned long irHoldStartMs = 0;
bool  irWaitRelease = false;

bool  uiBrake     = false;
bool  launchArmed = false;
bool  braking     = false;

unsigned long crankStartMs = 0;
unsigned long flareUntilMs = 0;
unsigned long lastSample   = 0;
unsigned long lastPrint    = 0;

String cmdBuf = "";

// ---------- Calibration & ADC Helpers ----------
uint16_t computeChecksum(const CalData &c) {
  uint32_t h = c.magic;
  h = h * 31u + (uint32_t)roundf(c.adcMin * 10.0f);
  h = h * 31u + (uint32_t)roundf(c.adcMax * 10.0f);
  h = h * 31u + c.potInvert;
  h = h * 31u + c.irActiveLow;
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
    adcMin      = cal.adcMin;
    adcMax      = cal.adcMax;
    potInvert   = (cal.potInvert == 1);
    irActiveLow = (cal.irActiveLow != 0);
  }
}

void saveCalibration() {
  CalData cal;
  cal.magic       = CAL_MAGIC;
  cal.adcMin      = adcMin;
  cal.adcMax      = adcMax;
  cal.potInvert   = potInvert ? 1 : 0;
  cal.irActiveLow = irActiveLow ? 1 : 0;
  cal.checksum    = computeChecksum(cal);
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
  // Reject floating-pin / violent electrical spikes across trimmed window
  int spread = s[SAMPLES - 1 - TRIM] - s[TRIM];
  if (spread > POT_SPREAD_MAX) {
    return false;
  }
  long sum = 0;
  for (int i = TRIM; i < SAMPLES - TRIM; i++) sum += s[i];
  outVal = (float)sum / (SAMPLES - 2 * TRIM);
  return true;
}

void startEngine(unsigned long now) {
  if (engState == ENG_OFF) {
    engState = ENG_CRANKING;
    crankStartMs = now;
    launchArmed = false;
  }
}

void stopEngine() {
  engState = ENG_OFF;
  launchArmed = false;
  braking = false;
}

void handleCommand(String cmd, unsigned long now) {
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
    adcMin      = 6.0f;
    adcMax      = 1017.0f;
    potInvert   = false;
    irActiveLow = true;
    saveCalibration();
  } else if (cmd == "POT_INVERT") {
    potInvert = !potInvert;
    saveCalibration();
  } else if (cmd == "IR_INVERT") {
    irActiveLow = !irActiveLow;
    irRawPrev = (digitalRead(IR_PIN) == (irActiveLow ? LOW : HIGH));
    irDetected = irRawPrev;
    irWaitRelease = false;
    irHoldEligibleShutoff = false;
    saveCalibration();
  } else if (cmd == "ENG_TOGGLE") {
    if (engState == ENG_OFF) startEngine(now);
    else stopEngine();
  } else if (cmd == "BRAKE_ON") {
    uiBrake = true;
  } else if (cmd == "BRAKE_OFF") {
    uiBrake = false;
  }
}

void pollSerialCommands(unsigned long now) {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdBuf.length() > 0) {
        handleCommand(cmdBuf, now);
        cmdBuf = "";
      }
    } else if (cmdBuf.length() < 32) {
      cmdBuf += c;
    }
  }
}

void updateIR(unsigned long now) {
  bool raw = (digitalRead(IR_PIN) == (irActiveLow ? LOW : HIGH));
  if (raw != irRawPrev) {
    irRawPrev = raw;
    irChangeMs = now;
  }
  if ((now - irChangeMs) >= 50) {
    if (raw != irDetected) {
      irDetected = raw;
      if (!irDetected) {
        irWaitRelease = false;
        irHoldEligibleShutoff = false;
      } else {
        if (engState == ENG_OFF && !irWaitRelease) {
          startEngine(now);
          irWaitRelease = true;
        } else if (engState == ENG_RUNNING && !irWaitRelease) {
          irHoldStartMs = now;
          irHoldEligibleShutoff = (speedKmh < 2.0f && throttle < 0.12f);
        }
      }
    }
  }

  if (irDetected && (throttle >= 0.12f || speedKmh >= 2.0f)) {
    irHoldEligibleShutoff = false;
  }

  if (engState == ENG_RUNNING && irDetected && !irWaitRelease &&
      irHoldEligibleShutoff && (now - irHoldStartMs) >= SHUTOFF_HOLD_MS) {
    stopEngine();
    irWaitRelease = true;
    irHoldEligibleShutoff = false;
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

  // Crisp endpoint snap deadzones so idle sits at 0% and full turn locks at 100%
  if (x <= 0.02f) x = 0.0f;
  else if (x >= 0.985f) x = 1.0f;
  else x = (x - 0.02f) / 0.965f;

  throttle = constrain(x, 0.0f, 1.0f);
}

void updateCarAndEngine(float dt, unsigned long now) {
  bool holdInput = (irDetected && !irWaitRelease) || uiBrake;

  if (engState == ENG_OFF) {
    launchArmed = false;
    braking = false;
    speedKmh = max(0.0f, speedKmh - 120.0f * dt);
    rpm += (0.0f - rpm) * (1.0f - expf(-12.0f * dt));
    if (rpm < 20.0f) rpm = 0.0f;
    gear = 0;
    return;
  }

  if (engState == ENG_CRANKING) {
    unsigned long elapsed = now - crankStartMs;
    launchArmed = false;
    braking = false;
    speedKmh = 0.0f;
    gear = 0;
    rpm = 270.0f + 55.0f * sinf(elapsed * 0.042f);
    if (elapsed >= CRANK_TIME_MS) {
      engState = ENG_RUNNING;
      flareUntilMs = now + FLARE_TIME_MS;
      rpm = 2150.0f;
    }
    return;
  }

  if (holdInput && speedKmh < 15.0f && throttle >= 0.18f) {
    launchArmed = true;
    braking = true;
  } else {
    launchArmed = false;
    braking = holdInput;
  }

  float targetSpeed = 0.0f;
  if (launchArmed) {
    speedKmh = max(0.0f, speedKmh - 180.0f * dt);
  } else if (braking) {
    speedKmh = max(0.0f, speedKmh - 155.0f * dt);
  } else {
    targetSpeed = (throttle <= 0.005f) ? 0.0f : (throttle * MAX_SPEED_KMH);
    float alphaSpd = 1.0f - expf(-10.0f * dt);
    speedKmh += (targetSpeed - speedKmh) * alphaSpd;
    if (fabs(targetSpeed - speedKmh) < 0.25f) speedKmh = targetSpeed;
    if (targetSpeed == 0.0f && speedKmh < 0.3f) speedKmh = 0.0f;
  }

  while (gear < 7 && speedKmh >= UP_KMH[gear]) gear++;
  while (gear > 0 && speedKmh < DOWN_KMH[gear - 1]) gear--;

  float targetRpm = IDLE_RPM;
  if (launchArmed) {
    gear = 0;
    targetRpm = LAUNCH_RPM + (((now / 48) % 2 == 0) ? 75.0f : -75.0f);
  } else {
    float frac = (speedKmh - GEAR_MIN_KMH[gear]) / (GEAR_MAX_KMH[gear] - GEAR_MIN_KMH[gear]);
    frac = constrain(frac, 0.0f, 1.0f);
    targetRpm = GEAR_MIN_RPM[gear] + frac * (GEAR_MAX_RPM[gear] - GEAR_MIN_RPM[gear]);
    if (now < flareUntilMs) {
      float flareFrac = (float)(flareUntilMs - now) / (float)FLARE_TIME_MS;
      targetRpm = max(targetRpm, IDLE_RPM + 1500.0f * flareFrac);
    }
  }

  float alphaRpm = 1.0f - expf(-15.0f * dt);
  rpm += (targetRpm - rpm) * alphaRpm;
  if (fabs(targetRpm - rpm) < 5.0f) rpm = targetRpm;
}

void setup() {
  Serial.begin(115200);
  pinMode(IR_PIN, INPUT_PULLUP);
  loadCalibration();
  float initVal = 0.0f;
  if (readPotClean(initVal)) filtered = initVal;
  else filtered = (float)analogRead(POT_PIN);
  irRawPrev = (digitalRead(IR_PIN) == (irActiveLow ? LOW : HIGH));
  irDetected = irRawPrev;
  lastSample = millis();
}

void loop() {
  unsigned long now = millis();
  pollSerialCommands(now);
  updateIR(now);

  if (now - lastSample >= SAMPLE_INTERVAL_MS) {
    float dt = (now - lastSample) / 1000.0f;
    if (dt > 0.05f) dt = 0.05f;
    lastSample = now;
    updateThrottle();
    updateCarAndEngine(dt, now);
  }

  if (now - lastPrint >= PRINT_INTERVAL_MS) {
    lastPrint = now;
    int rpmOut   = ((int)(rpm / 10.0f + 0.5f)) * 10;
    int speedOut = (int)(speedKmh + 0.5f);
    int thrPct   = (int)(throttle * 100.0f + 0.5f);
    int outMin   = (int)(calibrating ? calMin : adcMin);
    int outMax   = (int)(calibrating ? calMax : adcMax);

#if HUMAN_READABLE
    Serial.print(F("M5 | Eng: "));      Serial.print((int)engState);
    Serial.print(F(" | Gear: "));       Serial.print(gear + 1);
    Serial.print(F(" | RPM: "));        Serial.print(rpmOut);
    Serial.print(F(" | Speed: "));      Serial.print(speedOut);
    Serial.print(F(" km/h | Thr: "));   Serial.print(thrPct);
    Serial.print(F("% | IR: "));        Serial.print(irDetected ? 1 : 0);
    Serial.print(F(" | Launch: "));     Serial.println(launchArmed ? 1 : 0);
#else
    Serial.print("RPM:");        Serial.print(rpmOut);
    Serial.print(",Speed_x20:"); Serial.print(speedOut * 20);
    Serial.print(",Gear_x500:"); Serial.print((gear + 1) * 500);
    Serial.print(",Throttle:");  Serial.print(thrPct);
    Serial.print(",Eng:");       Serial.print((int)engState);
    Serial.print(",Launch:");    Serial.print(launchArmed ? 1 : 0);
    Serial.print(",Brake:");     Serial.print(braking ? 1 : 0);
    Serial.print(",IR:");        Serial.print(irDetected ? 1 : 0);
    Serial.print(",Inv:");       Serial.print(potInvert ? 1 : 0);
    Serial.print(",IrLow:");     Serial.print(irActiveLow ? 1 : 0);
    Serial.print(",Raw:");       Serial.print((int)filtered);
    Serial.print(",Cal:");       Serial.print(calibrating ? 1 : 0);
    Serial.print(",AdcMin:");    Serial.print(outMin);
    Serial.print(",AdcMax:");    Serial.print(outMax);
    Serial.print(",Redline:");   Serial.println((int)REDLINE_RPM);
#endif
  }
}
