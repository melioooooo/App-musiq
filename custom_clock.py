import asyncio
import time
import os
import io
import pypixelcolor
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Configuration
load_dotenv()
DEVICE_MAC = os.getenv("DEVICE_MAC", "95:0B:57:BF:8F:8D")
LOCATION = os.getenv("LOCATION", "Strasbourg")

class CustomClock:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = pypixelcolor.Client(mac_address)
        self.is_connected = False
        self.last_weather = None
        self.last_weather_fetch = 0

    def connect(self):
        print(f"Connecting to {self.mac_address}...")
        try:
            self.client.connect()
            self.is_connected = True
            print("Connected!")
        except Exception as e:
            print(f"Connection failed: {e}")

    def fetch_weather(self):
        """Fetches weather once an hour from wttr.in with retry backoff."""
        now = time.time()
        
        # If we have weather and it's less than an hour old, keep it
        if self.last_weather and (now - self.last_weather_fetch < 3600):
            return self.last_weather
            
        # If the last attempt failed, wait at least 5 minutes before retrying
        if not self.last_weather and (now - self.last_weather_fetch < 300):
            return None

        print(f"Fetching current weather for {LOCATION} (Attempting...)...")
        try:
            # Explicitly requesting location from env
            response = requests.get(f"https://wttr.in/{LOCATION}?format=j1", timeout=5)
            if response.status_code == 200:
                data = response.json()
                condition = data['current_condition'][0]['weatherCode']
                self.last_weather = condition
                self.last_weather_fetch = now
                print("Weather updated successfully.")
                return condition
            else:
                print(f"Weather server returned status: {response.status_code}")
        except Exception as e:
            print(f"Weather fetch failed (will retry in 5m): {e}")
        
        # Mark attempt time even on failure to trigger the 5m backoff
        self.last_weather_fetch = now
        return self.last_weather

    def draw_weather_pictogram(self, draw, code):
        """Draws a refined 16x32 weather pictogram on the left side, with night mode support."""
        code = int(code) if code else 113
        
        # Determine if it's night (e.g., between 7 PM and 7 AM)
        hour = int(time.strftime("%H"))
        is_night = hour >= 19 or hour < 7

        # Sunny / Clear
        if code == 113: 
            if is_night:
                # Moon: Crescent shape
                draw.ellipse([4, 12, 12, 20], fill=(240, 240, 240)) # Main circle
                draw.ellipse([7, 10, 15, 18], fill=(0, 0, 0)) # Masking circle to create crescent
            else:
                # Sun: Filled circle
                draw.ellipse([5, 13, 11, 19], fill=(255, 200, 0))
                # 8 rays around the sun
                # cardinal
                draw.point([(8, 11), (8, 21), (3, 16), (13, 16)], fill=(255, 180, 0))
                # diagonal
                draw.point([(5, 13), (11, 13), (5, 19), (11, 19)], fill=(255, 150, 0))
            
        # Cloudy / Mist
        elif code in [116, 119, 122, 143, 248, 260]:
            # Refined Fluffy Cloud (slightly darker at night)
            base_col = (100, 100, 120) if is_night else (180, 180, 180)
            draw.ellipse([3, 15, 10, 21], fill=base_col) # Left hump
            draw.ellipse([7, 16, 13, 22], fill=(base_col[0]-40, base_col[1]-40, base_col[2]-40)) # Right hump
            draw.ellipse([5, 13, 11, 18], fill=(base_col[0]+40, base_col[1]+40, base_col[2]+40)) # Top hump
            
        # Rain / Drizzle
        elif code in [176, 263, 266, 281, 284, 293, 296, 299, 302, 305, 308, 311]:
            # Cloud + raindrops
            draw.ellipse([3, 12, 12, 18], fill=(80, 80, 130) if is_night else (100, 100, 150))
            draw.point([(5, 20), (9, 21), (6, 23), (11, 24)], fill=(0, 150, 255))
            
        # Snow / Ice
        elif code in [179, 182, 185, 227, 230, 314, 317, 320, 323, 326, 329, 332]:
            # Snowflake-like dots
            draw.point([(8, 11), (5, 14), (11, 14), (8, 17), (5, 20), (11, 20), (8, 23)], fill=(255, 255, 255))

        # Thunder
        elif code in [200, 386, 389, 392]:
            # Dark cloud + bolt
            draw.ellipse([3, 12, 12, 18], fill=(40, 40, 60) if is_night else (60, 60, 80))
            draw.line([(8, 19), (6, 22), (10, 22), (8, 26)], fill=(255, 255, 0))
        
        else: # Default Cloud
            draw.ellipse([3, 14, 13, 20], fill=(100, 100, 100) if is_night else (150, 150, 150))

    def show_time(self, color="ffffff"):
        # Create a 32x32 black canvas
        img = Image.new('RGB', (32, 32), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 1. Fetch and Draw Weather (Left side: 0-15)
        weather_code = self.fetch_weather()
        self.draw_weather_pictogram(draw, weather_code)

        # 2. Draw Vertical Clock (Right side: 16-31)
        h = time.strftime("%H")
        m = time.strftime("%M")
        
        # Parse hex color
        try:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            text_color = (r, g, b)
        except:
            text_color = (255, 255, 255)

        # Try to load the VCR_OSD_MONO font
        try:
            import pypixelcolor
            font_path = os.path.join(pypixelcolor.__path__[0], 'fonts', 'VCR_OSD_MONO.ttf')
            # 15px fits slightly better in the 16px half than 16px
            font = ImageFont.truetype(font_path, 15)
        except:
            font = ImageFont.load_default()

        # Draw H and M aligned to the right half
        try:
            h_bbox = draw.textbbox((0, 0), h, font=font)
            m_bbox = draw.textbbox((0, 0), m, font=font)
            h_w = h_bbox[2] - h_bbox[0]
            m_w = m_bbox[2] - m_bbox[0]
            
            # Right half is x=16 to 31. We want a 1px border on the right, so width=15.
            # Center of right half (16-30) is x = 16 + (15 - width) // 2
            # Shifting minutes up to 15 to reduce the gap
            draw.text(((16 + (15 - h_w) // 2), 2), h, font=font, fill=text_color)
            draw.text(((16 + (15 - m_w) // 2), 15), m, font=font, fill=text_color)
        except:
            draw.text((18, 2), h, fill=text_color)
            draw.text((18, 16), m, fill=text_color)
            
        temp_path = "clock_weather.png"
        img.save(temp_path)
        
        print(f"Showing weather clock: {h}:{m} (Weather Code: {weather_code})")
        try:
            self.client.send_image(temp_path)
        except Exception as e:
            print(f"Failed to send image: {e}")

    def run(self, color="ffffff", interval=60):
        self.connect()
        if not self.is_connected:
            return

        print(f"Weather Clock running (Color: {color})... Press Ctrl+C to stop.")
        try:
            while True:
                self.show_time(color)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            self.client.disconnect()

if __name__ == "__main__":
    import sys
    color = sys.argv[1] if len(sys.argv) > 1 else "ffffff"
    clock = CustomClock(DEVICE_MAC)
    clock.run(color=color)
