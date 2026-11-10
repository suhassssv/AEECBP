import math
import time
from collections import deque

import serial
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from serial.tools import list_ports

# -------------------------------
# DASHBOARD CONFIGURATION
# -------------------------------

st.set_page_config(
    page_title="Vehicle Telemetry Dashboard",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* Pure Black Automotive Cockpit Background */
.stApp {
    background-color: #000000 !important;
    color: #ffffff;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Center and maximize cluster display */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1360px !important;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background-color: #080d16 !important;
    border-right: 1px solid #142236;
}

/* Metric card styling */
[data-testid="stMetric"] {
    background: #080f1a;
    border: 1px solid #16283f;
    padding: 12px 18px;
    border-radius: 12px;
}

[data-testid="stMetricValue"] {
    color: #38b6ff !important;
    font-weight: 700;
}

h1, h2, h3, p, label {
    color: #e0e8f5 !important;
}
</style>
""", unsafe_allow_html=True)


# -------------------------------
# CLUSTER SVG GENERATOR
# -------------------------------

def generate_cluster_svg(speed=65, rpm=5800, fuel=72, temp=85, voltage=13.8, odo="165376", left_turn=False, right_turn=False, park_brake=True, warning=False):
    """
    Renders an exact vector automotive cockpit gauge cluster matching the reference design:
    - Left small: Fuel gauge with E/F and fuel pump icon
    - Left main: Speedometer (0-220 km/h) with segmented tick ring and (P) icon
    - Center: Turn arrows, MID digital telemetry, and LCD odometer
    - Right main: Tachometer (0-8 x1000 RPM) with 0-6 blue ticks, 6-8 redline ticks, and (!) icon
    - Right small: Engine temperature/coolant gauge with C/H and thermometer icon
    - Curved binnacle hood, metallic cowls, and glowing neon-blue illuminated needles
    """
    w, h = 1240, 500
    
    # Dial Center Coordinates & Radii
    c_fuel = (105, 325, 68)
    c_speed = (370, 245, 175)
    c_tach = (870, 245, 175)
    c_temp = (1135, 325, 68)
    
    # Needle Rotation Angles (-130 deg to +130 deg = 260 deg total sweep)
    # Speedometer: 0 to 220 km/h
    speed_clamped = max(0.0, min(220.0, float(speed)))
    speed_deg = -130.0 + (speed_clamped / 220.0) * 260.0
    
    # Tachometer: 0 to 8000 RPM (0 to 8.0)
    rpm_k = max(0.0, min(8.0, float(rpm) / 1000.0))
    tach_deg = -130.0 + (rpm_k / 8.0) * 260.0
    
    # Fuel: 0 to 100% (-45 to +45 deg sweep)
    fuel_clamped = max(0.0, min(100.0, float(fuel)))
    fuel_deg = -45.0 + (fuel_clamped / 100.0) * 90.0
    
    # Coolant Temp: 40 to 120 C (-45 to +45 deg sweep)
    temp_clamped = max(40.0, min(120.0, float(temp)))
    temp_deg = -45.0 + ((temp_clamped - 40.0) / 80.0) * 90.0

    svg_parts = []
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" style="width:100%; max-width:{w}px; height:auto; display:block; margin:auto; background:#000000; font-family:'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; user-select:none;">''')
    
    # SVG Defs, Gradients, and Glow Filters
    svg_parts.append('''
    <defs>
        <!-- Blue Neon Glow -->
        <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur1"/>
            <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="blur2"/>
            <feMerge>
                <feMergeNode in="blur2"/>
                <feMergeNode in="blur1"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>

        <!-- Intense Needle Glow -->
        <filter id="needle-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur1"/>
            <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur2"/>
            <feMerge>
                <feMergeNode in="blur2"/>
                <feMergeNode in="blur1"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>

        <!-- Red Redline Glow -->
        <filter id="red-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur"/>
            <feMerge>
                <feMergeNode in="blur"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>

        <!-- Dial Face Radial Gradient -->
        <radialGradient id="dial-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#020408"/>
            <stop offset="65%" stop-color="#060c16"/>
            <stop offset="85%" stop-color="#0c1828"/>
            <stop offset="100%" stop-color="#12243a"/>
        </radialGradient>

        <!-- Outer Bezel Metal Gradient -->
        <linearGradient id="bezel-metal" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#4e5b6e"/>
            <stop offset="35%" stop-color="#222b37"/>
            <stop offset="70%" stop-color="#111620"/>
            <stop offset="100%" stop-color="#2a3646"/>
        </linearGradient>

        <!-- Sculpted Top Hood / Cowl Shade -->
        <linearGradient id="hood-cowl" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#6f819b" stop-opacity="0.85"/>
            <stop offset="45%" stop-color="#2b3543" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="#0a0e14" stop-opacity="0"/>
        </linearGradient>

        <!-- Binnacle Outer Enclosure Gradient -->
        <radialGradient id="cluster-bg" cx="50%" cy="25%" r="65%">
            <stop offset="0%" stop-color="#121824"/>
            <stop offset="50%" stop-color="#080c13"/>
            <stop offset="100%" stop-color="#010204"/>
        </radialGradient>

        <!-- Needle Luminous Blue Gradient -->
        <linearGradient id="needle-blue" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#e2f7ff"/>
            <stop offset="30%" stop-color="#38b6ff"/>
            <stop offset="100%" stop-color="#0052e0"/>
        </linearGradient>

        <!-- Hub Cap Metallic Finish -->
        <radialGradient id="hub-cap" cx="40%" cy="40%" r="60%">
            <stop offset="0%" stop-color="#4d5c70"/>
            <stop offset="60%" stop-color="#1a2330"/>
            <stop offset="100%" stop-color="#080c12"/>
        </radialGradient>

        <!-- Glowing Hub Core -->
        <radialGradient id="hub-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#c7f6ff"/>
            <stop offset="40%" stop-color="#2eb9ff"/>
            <stop offset="100%" stop-color="#0044cc"/>
        </radialGradient>
    </defs>
    ''')

    # 1. Main Dashboard Outer Binnacle / Housing
    svg_parts.append('''
    <!-- Outer Binnacle Housing -->
    <path d="M 40,445 C 65,210 220,50 620,35 C 1020,50 1175,210 1200,445 C 960,460 280,460 40,445 Z" 
          fill="url(#cluster-bg)" stroke="#1a2638" stroke-width="3"/>

    <!-- Top Metallic Hood Arch Highlight -->
    <path d="M 68,425 C 90,225 235,70 620,55 C 1005,70 1150,225 1172,425" 
          fill="none" stroke="#3d516c" stroke-width="2" opacity="0.6"/>

    <!-- Bottom Sill Highlight -->
    <path d="M 50,448 L 1190,448" stroke="#1c2c40" stroke-width="4"/>
    <path d="M 110,446 L 1130,446" stroke="#364c67" stroke-width="1.5" opacity="0.8"/>
    ''')

    # Helper function to render dial bezels & face
    def draw_dial_base(cx, cy, r, has_cowl=True):
        res = []
        res.append(f'<circle cx="{cx}" cy="{cy}" r="{r+14}" fill="url(#bezel-metal)" stroke="#090d14" stroke-width="2"/>')
        res.append(f'<circle cx="{cx}" cy="{cy}" r="{r+10}" fill="#080c14" stroke="#253549" stroke-width="1.5"/>')
        res.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#dial-grad)" stroke="#0e1724" stroke-width="1"/>')
        # Neon glowing ring around dial perimeter
        res.append(f'<circle cx="{cx}" cy="{cy}" r="{r-2}" fill="none" stroke="#2b9aff" stroke-width="2.5" opacity="0.85" filter="url(#neon-glow)"/>')
        res.append(f'<circle cx="{cx}" cy="{cy}" r="{r-2}" fill="none" stroke="#66c4ff" stroke-width="1" opacity="0.9"/>')
        
        # Upper metallic cowl (visor shading)
        if has_cowl:
            res.append(f'''
            <path d="M {cx - r - 8},{cy - 20} A {r + 10} {r + 10} 0 0 1 {cx + r + 8},{cy - 20} 
                     C {cx + r - 20},{cy - 70} {cx - r + 20},{cy - 70} {cx - r - 8},{cy - 20} Z"
                  fill="url(#hood-cowl)"/>
            <path d="M {cx - r - 4},{cy - 25} A {r + 6} {r + 6} 0 0 1 {cx + r + 4},{cy - 25}" 
                  fill="none" stroke="#5d728f" stroke-width="2" opacity="0.5"/>
            ''')
        return "\n".join(res)

    # 2. Left Small Dial (Fuel Gauge)
    fx, fy, fr = c_fuel
    svg_parts.append(draw_dial_base(fx, fy, fr, has_cowl=False))
    
    # Fuel Ticks (from -60 deg to +60 deg around top)
    for i in range(9):
        ang = -60 + i * 15
        rad = math.radians(ang)
        r1 = fr - 14 if (i % 2 == 0) else fr - 10
        r2 = fr - 4
        x1 = fx + r1 * math.sin(rad)
        y1 = fy - r1 * math.cos(rad)
        x2 = fx + r2 * math.sin(rad)
        y2 = fy - r2 * math.cos(rad)
        w = 2.5 if (i % 4 == 0) else 1.5
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#38b6ff" stroke-width="{w}" filter="url(#neon-glow)"/>')
    
    # Fuel labels E and F
    svg_parts.append(f'<text x="{fx-32}" y="{fy-18}" fill="#8cb9e6" font-size="12" font-weight="bold" text-anchor="middle">E</text>')
    svg_parts.append(f'<text x="{fx+32}" y="{fy-18}" fill="#8cb9e6" font-size="12" font-weight="bold" text-anchor="middle">F</text>')

    # Fuel Pump Icon at bottom
    svg_parts.append(f'''
    <!-- Fuel Pump Icon -->
    <g transform="translate({fx-10}, {fy+25}) scale(0.9)" filter="url(#neon-glow)">
        <path d="M 3,18 L 3,5 C 3,3.5 4,2.5 5.5,2.5 L 12.5,2.5 C 14,2.5 15,3.5 15,5 L 15,18 Z" fill="none" stroke="#38b6ff" stroke-width="1.6"/>
        <rect x="5.5" y="5" width="7" height="5" fill="#38b6ff" opacity="0.6"/>
        <path d="M 15,7 L 17,7 C 18,7 19,8 19,9 L 19,15 C 19,16 18,17 17.5,17 L 17.5,19" fill="none" stroke="#38b6ff" stroke-width="1.4"/>
        <circle cx="17.5" cy="6" r="1.2" fill="#38b6ff"/>
    </g>
    ''')

    # Fuel Needle
    svg_parts.append(f'''
    <g transform="rotate({fuel_deg:.1f}, {fx}, {fy})">
        <polygon points="{fx-3},{fy+5} {fx-1},{fy-fr+12} {fx},{fy-fr+8} {fx+1},{fy-fr+12} {fx+3},{fy+5}" 
                 fill="url(#needle-blue)" filter="url(#needle-glow)"/>
        <line x1="{fx}" y1="{fy}" x2="{fx}" y2="{fy-fr+10}" stroke="#ffffff" stroke-width="1" opacity="0.9"/>
    </g>
    <circle cx="{fx}" cy="{fy}" r="11" fill="url(#hub-cap)" stroke="#0a0f17" stroke-width="1.5"/>
    <circle cx="{fx}" cy="{fy}" r="5" fill="url(#hub-core)" filter="url(#neon-glow)"/>
    ''')

    # 3. Speedometer (Left Main Dial: 0 to 220 km/h)
    sx, sy, sr = c_speed
    svg_parts.append(draw_dial_base(sx, sy, sr, has_cowl=True))

    # Outer decorative segmented tick ring (from -130 to +130 deg)
    for i in range(105):
        ang = -130 + (i / 104.0) * 260
        rad = math.radians(ang)
        r1 = sr - 7
        r2 = sr - 3
        x1 = sx + r1 * math.sin(rad)
        y1 = sy - r1 * math.cos(rad)
        x2 = sx + r2 * math.sin(rad)
        y2 = sy - r2 * math.cos(rad)
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#2a90ff" stroke-width="1.2" opacity="0.75"/>')

    # Speedometer Major & Minor Ticks & Numbers (0 to 220)
    speed_steps = 44 # every 5 km/h
    for i in range(speed_steps + 1):
        spd = i * 5
        ang = -130 + (spd / 220.0) * 260
        rad = math.radians(ang)
        is_major = (spd % 20 == 0)
        is_mid = (spd % 10 == 0 and not is_major)
        
        if is_major:
            r1 = sr - 28
            r2 = sr - 12
            w = 2.8
            color = "#42d9ff"
            glow = 'filter="url(#neon-glow)"'
        elif is_mid:
            r1 = sr - 22
            r2 = sr - 12
            w = 1.8
            color = "#2a8bf2"
            glow = ""
        else:
            r1 = sr - 18
            r2 = sr - 12
            w = 1.2
            color = "#1f6ebd"
            glow = ""
            
        x1 = sx + r1 * math.sin(rad)
        y1 = sy - r1 * math.cos(rad)
        x2 = sx + r2 * math.sin(rad)
        y2 = sy - r2 * math.cos(rad)
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}" {glow}/>')
        
        # Major Numbers: 0, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220
        if is_major:
            rt = sr - 46
            xt = sx + rt * math.sin(rad)
            yt = sy - rt * math.cos(rad) + 5
            svg_parts.append(f'<text x="{xt:.1f}" y="{yt:.1f}" fill="#ffffff" font-size="16" font-weight="700" text-anchor="middle" filter="drop-shadow(0 0 2px #0088ff)">{spd}</text>')

    # Parking Brake Indicator (P) at bottom
    pb_color = "#38b6ff" if park_brake else "#1c324a"
    pb_glow = 'filter="url(#neon-glow)"' if park_brake else ''
    svg_parts.append(f'''
    <!-- Parking Brake Symbol -->
    <g transform="translate({sx}, {sy + 90})" {pb_glow}>
        <circle cx="0" cy="0" r="16" fill="none" stroke="{pb_color}" stroke-width="2"/>
        <path d="M -21,-7 C -23,-2 -23,2 -21,7" fill="none" stroke="{pb_color}" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M 21,-7 C 23,-2 23,2 21,7" fill="none" stroke="{pb_color}" stroke-width="2.2" stroke-linecap="round"/>
        <text x="0" y="5.5" fill="{pb_color}" font-size="14" font-weight="900" text-anchor="middle">P</text>
    </g>
    ''')

    # Speedometer Needle
    svg_parts.append(f'''
    <!-- Speedometer Needle -->
    <g transform="rotate({speed_deg:.1f}, {sx}, {sy})">
        <polygon points="{sx-5},{sy+14} {sx-1.5},{sy-sr+22} {sx},{sy-sr+16} {sx+1.5},{sy-sr+22} {sx+5},{sy+14}" 
                 fill="url(#needle-blue)" filter="url(#needle-glow)"/>
        <line x1="{sx}" y1="{sy}" x2="{sx}" y2="{sy-sr+18}" stroke="#ffffff" stroke-width="1.4" opacity="0.95"/>
    </g>
    <!-- Center Hub -->
    <circle cx="{sx}" cy="{sy}" r="22" fill="url(#hub-cap)" stroke="#090d14" stroke-width="2"/>
    <circle cx="{sx}" cy="{sy}" r="11" fill="url(#hub-core)" filter="url(#needle-glow)"/>
    ''')

    # 4. Center Multi-Information Display (MID)
    mx = 620
    lt_glow = 'filter="url(#neon-glow)"' if left_turn else 'opacity="0.25"'
    rt_glow = 'filter="url(#neon-glow)"' if right_turn else 'opacity="0.25"'
    svg_parts.append(f'''
    <!-- Center Console Area -->
    <path d="M 525,120 L 715,120 L 735,390 L 505,390 Z" fill="#060a12" stroke="#162335" stroke-width="1.5" opacity="0.9"/>
    <path d="M 535,122 L 705,122" stroke="#2a8fff" stroke-width="2" filter="url(#neon-glow)"/>
    <path d="M 520,388 L 720,388" stroke="#1a5599" stroke-width="1.5"/>

    <!-- Left Turn Arrow -->
    <g transform="translate(545, 150)" {lt_glow}>
        <polygon points="0,10 16,0 16,6 30,6 30,14 16,14 16,20" fill="#2bd9ff"/>
    </g>

    <!-- Right Turn Arrow -->
    <g transform="translate(665, 150)" {rt_glow}>
        <polygon points="30,10 14,0 14,6 0,6 0,14 14,14 14,20" fill="#2bd9ff"/>
    </g>

    <!-- Center Display Telemetry Info -->
    <g transform="translate({mx}, 235)">
        <text x="0" y="0" fill="#8cb9e6" font-size="13" font-weight="600" letter-spacing="2" text-anchor="middle">SPEED</text>
        <text x="0" y="38" fill="#ffffff" font-size="38" font-weight="900" text-anchor="middle" filter="drop-shadow(0 0 6px #0099ff)">{int(speed)}</text>
        <text x="0" y="58" fill="#42d9ff" font-size="12" font-weight="700" letter-spacing="1" text-anchor="middle">KM / H</text>
    </g>

    <!-- Digital Odometer Box -->
    <g transform="translate({mx}, 395)">
        <rect x="-65" y="-14" width="130" height="28" rx="4" fill="#040810" stroke="#1f4168" stroke-width="1.5"/>
        <text x="0" y="6" fill="#42d9ff" font-family="'Courier New', monospace, monospace" font-size="17" font-weight="900" letter-spacing="4" text-anchor="middle" filter="url(#neon-glow)">{odo}</text>
    </g>
    ''')

    # 5. Tachometer (Right Main Dial: 0 to 8 x 1000 RPM)
    tx, ty, tr = c_tach
    svg_parts.append(draw_dial_base(tx, ty, tr, has_cowl=True))

    # Outer decorative segmented tick ring (from -130 to +130 deg)
    for i in range(105):
        ang = -130 + (i / 104.0) * 260
        rad = math.radians(ang)
        r1 = tr - 7
        r2 = tr - 3
        x1 = tx + r1 * math.sin(rad)
        y1 = ty - r1 * math.cos(rad)
        x2 = tx + r2 * math.sin(rad)
        y2 = ty - r2 * math.cos(rad)
        # Redline on outer ring for 6 to 8 (i >= 78)
        color = "#ff4d4d" if i >= 78 else "#2a90ff"
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="1.2" opacity="0.8"/>')

    # Redline background arc (from 6 to 8: +65 deg to +130 deg)
    p_x1 = tx + (tr-22)*math.sin(math.radians(65))
    p_y1 = ty - (tr-22)*math.cos(math.radians(65))
    p_x2 = tx + (tr-22)*math.sin(math.radians(130))
    p_y2 = ty - (tr-22)*math.cos(math.radians(130))
    svg_parts.append(f'''
    <!-- Redline Danger Zone Arc -->
    <path d="M {p_x1:.1f},{p_y1:.1f} A {tr-22} {tr-22} 0 0 1 {p_x2:.1f},{p_y2:.1f}"
          fill="none" stroke="#ff3838" stroke-width="6" opacity="0.85" filter="url(#red-glow)"/>
    ''')

    # Tachometer Major & Minor Ticks & Numbers (0 to 8)
    tach_steps = 40 # every 0.2k RPM
    for i in range(tach_steps + 1):
        rpm_val = i * 0.2
        ang = -130 + (rpm_val / 8.0) * 260
        rad = math.radians(ang)
        is_major = (i % 5 == 0)
        is_redline = (rpm_val >= 6.0)
        
        if is_redline:
            main_color = "#ff4444"
            mid_color = "#e63333"
            glow_attr = 'filter="url(#red-glow)"'
        else:
            main_color = "#42d9ff"
            mid_color = "#2a8bf2"
            glow_attr = 'filter="url(#neon-glow)"'

        if is_major:
            r1 = tr - 28
            r2 = tr - 12
            w = 2.8
            color = main_color
            glow = glow_attr
        else:
            r1 = tr - 20
            r2 = tr - 12
            w = 1.4
            color = mid_color
            glow = ""
            
        x1 = tx + r1 * math.sin(rad)
        y1 = ty - r1 * math.cos(rad)
        x2 = tx + r2 * math.sin(rad)
        y2 = ty - r2 * math.cos(rad)
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}" {glow}/>')
        
        # Major Numbers: 0, 1, 2, 3, 4, 5, 6, 7, 8
        if is_major:
            num = int(round(rpm_val))
            rt = tr - 46
            xt = tx + rt * math.sin(rad)
            yt = ty - rt * math.cos(rad) + 5
            num_color = "#ff4444" if (num >= 6) else "#ffffff"
            text_glow = 'filter="drop-shadow(0 0 3px #ff2222)"' if (num >= 6) else 'filter="drop-shadow(0 0 2px #0088ff)"'
            svg_parts.append(f'<text x="{xt:.1f}" y="{yt:.1f}" fill="{num_color}" font-size="17" font-weight="700" text-anchor="middle" {text_glow}>{num}</text>')

    # Warning Indicator (!) at bottom
    warn_color = "#ff4444" if warning else "#38b6ff"
    warn_glow = 'filter="url(#red-glow)"' if warning else 'filter="url(#neon-glow)"'
    svg_parts.append(f'''
    <!-- Brake / Warning Symbol -->
    <g transform="translate({tx}, {ty + 90})" {warn_glow}>
        <circle cx="0" cy="0" r="16" fill="none" stroke="{warn_color}" stroke-width="2"/>
        <path d="M -21,-7 C -23,-2 -23,2 -21,7" fill="none" stroke="{warn_color}" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M 21,-7 C 23,-2 23,2 21,7" fill="none" stroke="{warn_color}" stroke-width="2.2" stroke-linecap="round"/>
        <text x="0" y="5.5" fill="{warn_color}" font-size="15" font-weight="900" text-anchor="middle">!</text>
    </g>
    ''')

    # Tachometer Needle
    svg_parts.append(f'''
    <!-- Tachometer Needle -->
    <g transform="rotate({tach_deg:.1f}, {tx}, {ty})">
        <polygon points="{tx-5},{ty+14} {tx-1.5},{ty-tr+22} {tx},{ty-tr+16} {tx+1.5},{ty-tr+22} {tx+5},{ty+14}" 
                 fill="url(#needle-blue)" filter="url(#needle-glow)"/>
        <line x1="{tx}" y1="{ty}" x2="{tx}" y2="{ty-tr+18}" stroke="#ffffff" stroke-width="1.4" opacity="0.95"/>
    </g>
    <!-- Center Hub -->
    <circle cx="{tx}" cy="{ty}" r="22" fill="url(#hub-cap)" stroke="#090d14" stroke-width="2"/>
    <circle cx="{tx}" cy="{ty}" r="11" fill="url(#hub-core)" filter="url(#needle-glow)"/>
    ''')

    # 6. Right Small Dial (Engine Coolant Temperature / Voltage)
    ex, ey, er = c_temp
    svg_parts.append(draw_dial_base(ex, ey, er, has_cowl=False))
    
    # Temp Ticks (from -60 deg to +60 deg around top)
    for i in range(9):
        ang = -60 + i * 15
        rad = math.radians(ang)
        r1 = er - 14 if (i % 2 == 0) else er - 10
        r2 = er - 4
        x1 = ex + r1 * math.sin(rad)
        y1 = ey - r1 * math.cos(rad)
        x2 = ex + r2 * math.sin(rad)
        y2 = ey - r2 * math.cos(rad)
        color = "#ff4444" if i >= 7 else "#38b6ff"
        w = 2.5 if (i % 4 == 0) else 1.5
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}" filter="url(#neon-glow)"/>')
    
    # Temp labels C and H
    svg_parts.append(f'<text x="{ex-32}" y="{ey-18}" fill="#8cb9e6" font-size="12" font-weight="bold" text-anchor="middle">C</text>')
    svg_parts.append(f'<text x="{ex+32}" y="{ey-18}" fill="#ff6b6b" font-size="12" font-weight="bold" text-anchor="middle">H</text>')

    # Coolant Temperature Icon at bottom
    svg_parts.append(f'''
    <!-- Engine Coolant Temp Icon -->
    <g transform="translate({ex}, {ey+25})" filter="url(#neon-glow)">
        <rect x="-2" y="-12" width="4" height="12" rx="2" fill="none" stroke="#38b6ff" stroke-width="1.4"/>
        <circle cx="0" cy="2" r="4.5" fill="#38b6ff" stroke="#38b6ff" stroke-width="1"/>
        <line x1="2" y1="-9" x2="5" y2="-9" stroke="#38b6ff" stroke-width="1.2"/>
        <line x1="2" y1="-5" x2="5" y2="-5" stroke="#38b6ff" stroke-width="1.2"/>
        <path d="M -10,8 Q -5,6 0,8 Q 5,10 10,8" fill="none" stroke="#38b6ff" stroke-width="1.4"/>
        <path d="M -10,12 Q -5,10 0,12 Q 5,14 10,12" fill="none" stroke="#38b6ff" stroke-width="1.4"/>
    </g>
    ''')

    # Temp Needle
    svg_parts.append(f'''
    <g transform="rotate({temp_deg:.1f}, {ex}, {ey})">
        <polygon points="{ex-3},{ey+5} {ex-1},{ey-er+12} {ex},{ey-er+8} {ex+1},{ey-er+12} {ex+3},{ey+5}" 
                 fill="url(#needle-blue)" filter="url(#needle-glow)"/>
        <line x1="{ex}" y1="{ey}" x2="{ex}" y2="{ey-er+10}" stroke="#ffffff" stroke-width="1" opacity="0.9"/>
    </g>
    <circle cx="{ex}" cy="{ey}" r="11" fill="url(#hub-cap)" stroke="#0a0f17" stroke-width="1.5"/>
    <circle cx="{ex}" cy="{ey}" r="5" fill="url(#hub-core)" filter="url(#neon-glow)"/>
    ''')

    svg_parts.append('</svg>')
    svg_str = "".join(svg_parts)
    # Wrap in HTML so it renders in the Streamlit component iframe with black bg
    html = f'<html><body style="margin:0;padding:0;background:#000;overflow:hidden;">{svg_str}</body></html>'
    return html


# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------

if "connection" not in st.session_state:
    st.session_state.connection = None

if "history" not in st.session_state:
    st.session_state.history = deque(maxlen=300)

BAUD_RATE = 115200  # must match Serial.begin() in the Arduino sketch

if "last_rpm" not in st.session_state:
    st.session_state.last_rpm = 0

if "last_speed" not in st.session_state:
    st.session_state.last_speed = 0

if "last_gear" not in st.session_state:
    st.session_state.last_gear = 1

if "last_throttle" not in st.session_state:
    st.session_state.last_throttle = 0

if "last_rx" not in st.session_state:
    st.session_state.last_rx = 0.0  # time the last valid packet arrived

if "rx_buffer" not in st.session_state:
    st.session_state.rx_buffer = ""

if "last_raw" not in st.session_state:
    st.session_state.last_raw = None

if "cal_active" not in st.session_state:
    st.session_state.cal_active = False

if "cal_min" not in st.session_state:
    st.session_state.cal_min = 6

if "cal_max" not in st.session_state:
    st.session_state.cal_max = 1017

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = False

if "demo_rpm" not in st.session_state:
    st.session_state.demo_rpm = 5800

if "demo_speed" not in st.session_state:
    st.session_state.demo_speed = 65


# -------------------------------
# SIDEBAR CONTROLS
# -------------------------------

st.sidebar.title("SYSTEM CONNECTION")

if st.sidebar.button("🔄 Refresh Ports"):
    st.rerun()

ports = list(list_ports.comports())
port_dict = {p.device: f"{p.device} ({p.description})" for p in ports}

# Auto-detect Arduino or USB serial port
default_idx = 0
for idx, p in enumerate(ports):
    desc = (p.description or "").lower()
    hwid = (p.hwid or "").lower()
    dev = (p.device or "").lower()
    if "com5" in dev or any(k in desc or k in hwid for k in ["arduino", "ch340", "ftdi", "usb serial", "usb-serial"]):
        default_idx = idx
        break

if ports:
    selected_port = st.sidebar.selectbox(
        "Select Arduino COM Port",
        options=[p.device for p in ports],
        format_func=lambda dev: port_dict.get(dev, dev),
        index=default_idx
    )
else:
    selected_port = None
    st.sidebar.warning("Arduino not detected")

col_btn1, col_btn2 = st.sidebar.columns(2)

with col_btn1:
    connect_clicked = st.button("CONNECT", disabled=(selected_port is None), width="stretch")
with col_btn2:
    disconnect_clicked = st.button("DISCONNECT", width="stretch")

if connect_clicked:
    try:
        if st.session_state.connection:
            st.session_state.connection.close()

        st.session_state.connection = serial.Serial(
            selected_port,
            BAUD_RATE,
            timeout=0
        )

        time.sleep(2)
        st.session_state.connection.reset_input_buffer()
        st.session_state.history.clear()
        st.session_state.rx_buffer = ""
        st.session_state.last_rx = 0.0
        st.rerun()

    except Exception as e:
        err_msg = str(e)
        if "PermissionError" in err_msg or "Access is denied" in err_msg:
            st.sidebar.error(f"⚠️ {selected_port} is currently locked! Please close the Serial Monitor / Plotter in Arduino IDE.")
        else:
            st.sidebar.error(err_msg)

if disconnect_clicked:
    if st.session_state.connection:
        st.session_state.connection.close()

    st.session_state.connection = None
    st.rerun()

connected = (
    st.session_state.connection is not None
    and st.session_state.connection.is_open
)

if connected:
    st.sidebar.success("● CONNECTED")
else:
    st.sidebar.error("● DISCONNECTED")

# Knob Calibration controls in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Knob Calibration")
st.sidebar.caption("For knobs with limited travel: Start, sweep full min → max, then Save.")

cal_c1, cal_c2 = st.sidebar.columns(2)
with cal_c1:
    if st.button("🎯 Start", disabled=not connected, width="stretch"):
        try:
            st.session_state.connection.write(b"CAL_START\n")
            st.session_state.cal_active = True
        except Exception as e:
            st.sidebar.error(f"Calibration start failed: {e}")
with cal_c2:
    if st.button("✅ Save", disabled=not connected, width="stretch"):
        try:
            st.session_state.connection.write(b"CAL_SAVE\n")
            st.session_state.cal_active = False
        except Exception as e:
            st.sidebar.error(f"Calibration save failed: {e}")

if st.sidebar.button("↺ Reset Default Range", disabled=not connected, width="stretch"):
    try:
        st.session_state.connection.write(b"CAL_RESET\n")
        st.session_state.cal_active = False
    except Exception as e:
        st.sidebar.error(f"Calibration reset failed: {e}")

# Demo / Simulation Mode in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("🕹️ Simulation & Controls")
_new_demo = st.sidebar.toggle("Enable Manual / Demo Sliders", value=st.session_state.demo_mode)
if _new_demo != st.session_state.demo_mode:
    st.session_state.history.clear()  # avoid mixing live and demo timestamps
st.session_state.demo_mode = _new_demo

if st.session_state.demo_mode:
    st.session_state.demo_rpm = st.sidebar.slider("RPM", 0, 8000, int(st.session_state.last_rpm), 50)
    st.session_state.demo_speed = st.sidebar.slider("Speed (KM/H)", 0, 250, int(st.session_state.last_speed), 1)
    sim_fuel = st.sidebar.slider("Fuel Level (%)", 0, 100, 75, 1)
    sim_temp = st.sidebar.slider("Coolant Temp (°C)", 40, 120, 85, 1)
else:
    sim_fuel = 75
    sim_temp = 85


# -------------------------------
# LIVE COCKPIT DASHBOARD
# -------------------------------

def parse_telemetry_line(raw_line, default_gear=1, default_throttle=0):
    """
    Parse a single serial telemetry line into
    (t_sec, rpm, speed, gear, throttle, meta).
    Supports:
      1) 5-column CSV: elapsed_ms,rpm,speed_kmh,gear,throttle_pct
      2) Key:Value format: RPM:650,Speed_x20:0,Gear_x500:500,Throttle:0,...
    Returns None if the line is invalid or fails sanity checks.
    """
    line = raw_line.strip()
    if not line:
        return None

    parts = [p.strip() for p in line.split(",") if p.strip()]
    t_sec = None
    rpm = None
    speed = None
    gear = default_gear
    throttle = default_throttle
    meta = {}

    if any(":" in p for p in parts):
        kv = {}
        for p in parts:
            if ":" not in p:
                continue
            k, v = p.split(":", 1)
            try:
                kv[k.strip().lower()] = float(v.strip())
            except ValueError:
                continue

        if "rpm" not in kv:
            return None

        rpm = int(round(kv["rpm"]))
        if "speed_x20" in kv:
            speed = int(round(kv["speed_x20"] / 20.0))
        elif "speed" in kv:
            speed = int(round(kv["speed"]))
        else:
            return None

        if "gear_x500" in kv:
            gear = int(round(kv["gear_x500"] / 500.0))
        elif "gear" in kv:
            gear = int(round(kv["gear"]))

        if "throttle" in kv:
            throttle = int(round(kv["throttle"]))
        elif "thr" in kv:
            throttle = int(round(kv["thr"]))

        if "ms" in kv:
            t_sec = kv["ms"] / 1000.0
        elif "elapsed_ms" in kv:
            t_sec = kv["elapsed_ms"] / 1000.0

        for mkey in ("raw", "cal", "adcmin", "adcmax"):
            if mkey in kv:
                meta[mkey] = int(round(kv[mkey]))
    elif len(parts) == 5:
        try:
            t_sec = float(parts[0]) / 1000.0
            rpm = int(round(float(parts[1])))
            speed = int(round(float(parts[2])))
            gear = int(round(float(parts[3])))
            throttle = int(round(float(parts[4])))
        except ValueError:
            return None
    else:
        return None

    # sanity limits: drop corrupted packets
    if not (0 <= rpm <= 9000 and 0 <= speed <= 400 and 0 <= gear <= 8):
        return None
    throttle = max(0, min(100, throttle))

    return t_sec, rpm, speed, gear, throttle, meta


@st.fragment(run_every=0.5)
def update_dashboard():
    conn = st.session_state.connection

    # Read from live Arduino serial port.
    # Bytes are buffered so a half-received line is never parsed.
    if conn and conn.is_open:
        try:
            if conn.in_waiting:
                chunk = conn.read(conn.in_waiting).decode("utf-8", errors="ignore")
                st.session_state.rx_buffer += chunk

            buf = st.session_state.rx_buffer
            if "\n" in buf:
                *lines, rest = buf.split("\n")
                st.session_state.rx_buffer = rest[-200:]  # keep partial line, cap size

                for line in lines:
                    parsed = parse_telemetry_line(
                        line,
                        default_gear=st.session_state.last_gear,
                        default_throttle=st.session_state.last_throttle,
                    )
                    if parsed is None:
                        continue

                    t_sec, rpm, speed, gear, throttle, meta = parsed
                    if t_sec is None:
                        t_sec = time.time()
                        if st.session_state.history and t_sec <= st.session_state.history[-1]["time"]:
                            t_sec = st.session_state.history[-1]["time"] + 0.05

                    st.session_state.last_rpm = rpm
                    st.session_state.last_speed = speed
                    st.session_state.last_gear = gear
                    st.session_state.last_throttle = throttle
                    st.session_state.last_rx = time.time()

                    if "raw" in meta:
                        st.session_state.last_raw = meta["raw"]
                    if "cal" in meta:
                        st.session_state.cal_active = (meta["cal"] == 1)
                    if "adcmin" in meta:
                        st.session_state.cal_min = meta["adcmin"]
                    if "adcmax" in meta:
                        st.session_state.cal_max = meta["adcmax"]

                    st.session_state.history.append({
                        "time": t_sec,
                        "rpm": rpm,
                        "speed": speed
                    })
            elif len(buf) > 500:
                st.session_state.rx_buffer = ""  # no newline for ages -> wrong baud / garbage

        except Exception as e:
            st.error(f"Serial communication error: {e}")

    # Determine values to display
    if st.session_state.demo_mode:
        curr_rpm = st.session_state.demo_rpm
        curr_speed = st.session_state.demo_speed
        curr_gear = st.session_state.last_gear
        curr_throttle = st.session_state.last_throttle
        fuel_lvl = sim_fuel
        temp_val = sim_temp

        # In demo mode, also feed the history deque so the graphs work
        st.session_state.history.append({
            "time": time.time(),
            "rpm": curr_rpm,
            "speed": curr_speed
        })
    else:
        curr_rpm = st.session_state.last_rpm
        curr_speed = st.session_state.last_speed
        curr_gear = st.session_state.last_gear
        curr_throttle = st.session_state.last_throttle
        fuel_lvl = sim_fuel
        # Coolant warms up a little with throttle load (purely cosmetic)
        temp_val = 85 + int(curr_throttle * 0.1)

    receiving = (time.time() - st.session_state.last_rx) < 2.0

    # Warning alert when RPM is near redline (>6500)
    is_warning = curr_rpm >= 6500
    is_park_brake = curr_speed < 5

    # Render exact instrument cluster SVG
    cluster_svg = generate_cluster_svg(
        speed=curr_speed,
        rpm=curr_rpm,
        fuel=fuel_lvl,
        temp=temp_val,
        voltage=13.8,
        odo="165376",
        left_turn=False,
        right_turn=False,
        park_brake=is_park_brake,
        warning=is_warning
    )

    components.html(cluster_svg, height=460, scrolling=False)

    # Secondary Digital Telemetry Bar below cluster
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("VEHICLE SPEED", f"{int(curr_speed)} KM/H")
    col2.metric("ENGINE RPM", f"{int(curr_rpm):,} RPM")
    col3.metric("GEAR", f"{int(curr_gear)}")
    col4.metric("THROTTLE", f"{int(curr_throttle)} %")
    if not connected:
        status = "WAITING LINK"
    elif receiving:
        status = "LIVE"
    else:
        status = "NO DATA"
    col5.metric("SYSTEM STATUS", status)

    if connected and st.session_state.last_raw is not None:
        if st.session_state.cal_active:
            st.info(
                f"🎯 Calibration Active — Sweep your knob from full MIN to full MAX, then click **✅ Save** in the sidebar. "
                f"| Live Raw ADC: `{st.session_state.last_raw}` | Captured Min: `{st.session_state.cal_min}` | Captured Max: `{st.session_state.cal_max}`"
            )
        else:
            st.caption(
                f"Potentiometer ADC: `{st.session_state.last_raw}` | Active Range: `[{st.session_state.cal_min} .. {st.session_state.cal_max}]`"
            )

    # Expandable history graphs
    with st.expander("📈 Telemetry Log & Graphs", expanded=True):
        if len(st.session_state.history) > 1:
            df = pd.DataFrame(list(st.session_state.history))
            df["time"] = df["time"] - df["time"].iloc[0]
            g1, g2 = st.columns(2)
            with g1:
                st.caption("Engine RPM")
                st.line_chart(df.set_index("time")[["rpm"]], y_min=0, y_max=8000, height=250)
            with g2:
                st.caption("Vehicle speed (km/h)")
                st.line_chart(df.set_index("time")[["speed"]], y_min=0, y_max=260, height=250)
        else:
            st.caption("Live graphs will plot once telemetry packets arrive.")


# Run live dashboard
update_dashboard()
