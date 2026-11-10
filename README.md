# AEECBP — Vehicle Telemetry Cockpit Dashboard

Automotive digital instrument cluster for Arduino (`A0` potentiometer) featuring:
- **Vercel Web Serial App (`index.html`)** — Deploy directly to Vercel and connect your browser (Chrome / Edge) straight to the Arduino over USB at `115200` baud.
- **Arduino Sketch (`AEECBP.ino`)** — Direct responsive knob-to-speed/RPM mapping (`0–220 km/h`, `650–7100 RPM`, Gears `1–8`), `Throttle %` telemetry, and EEPROM-backed min/max knob calibration (`CAL_START`, `CAL_SAVE`, `CAL_RESET`).
- **Local Python Dashboard (`local_streamlit/dashboard.py`)** — Optional local Streamlit version using `pyserial`.

## Deploy to Vercel
1. Import `https://github.com/suhassssv/AEECBP` in Vercel.
2. Leave Framework Preset as **Other** (static `index.html` at repository root).
3. Deploy and open the HTTPS URL in **Chrome** or **Edge**, then click **CONNECT** and select your Arduino COM port.

## Local Streamlit Version (Optional)
```bash
pip install -r local_streamlit/requirements.txt
streamlit run local_streamlit/dashboard.py
```
