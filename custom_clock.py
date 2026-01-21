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
        """Draws a highly granular 16x32 weather pictogram on the left side."""
        code = int(code) if code else 113
        hour = int(time.strftime("%H"))
        is_night = hour >= 19 or hour < 7

        # 1. SUNNY / CLEAR
        if code == 113: 
            if is_night:
                # Moon
                draw.ellipse([4, 12, 12, 20], fill=(240, 240, 240))
                draw.ellipse([7, 10, 15, 18], fill=(0, 0, 0))
            else:
                # Sun
                draw.ellipse([5, 13, 11, 19], fill=(255, 200, 0))
                draw.point([(8, 11), (8, 21), (3, 16), (13, 16)], fill=(255, 180, 0))
                draw.point([(5, 13), (11, 13), (5, 19), (11, 19)], fill=(255, 150, 0))

        # 2. PARTLY CLOUDY
        elif code == 116:
            if is_night:
                # Small Moon behind cloud
                draw.ellipse([7, 11, 13, 17], fill=(200, 200, 200))
                draw.ellipse([9, 10, 15, 15], fill=(0, 0, 0))
            else:
                # Small Sun behind cloud
                draw.ellipse([8, 11, 13, 16], fill=(255, 200, 0))
            # Cloud
            draw.ellipse([3, 15, 10, 21], fill=(120, 120, 130) if is_night else (180, 180, 180))
            draw.ellipse([6, 14, 13, 19], fill=(80, 80, 90) if is_night else (140, 140, 150))

        # 3. CLOUDY / OVERCAST
        elif code in [119, 122]:
            if is_night:
                # Tiny moon peeking from top-right
                draw.ellipse([9, 10, 14, 15], fill=(180, 180, 180))
                draw.ellipse([11, 9, 16, 13], fill=(0, 0, 0))
            base = (80, 80, 100) if is_night else (160, 160, 170)
            draw.ellipse([3, 15, 10, 21], fill=base)
            draw.ellipse([7, 16, 13, 22], fill=(base[0]-20, base[1]-20, base[2]-20))
            draw.ellipse([5, 13, 11, 18], fill=(base[0]+20, base[1]+20, base[2]+20))

        # 4. FOG / MIST
        elif code in [143, 248, 260]:
            if is_night:
                draw.ellipse([8, 11, 12, 15], fill=(60, 60, 70))
            col = (80, 80, 100) if is_night else (180, 180, 200)
            draw.line([(4, 14), (12, 14)], fill=col)
            draw.line([(3, 17), (11, 17)], fill=col)
            draw.line([(5, 20), (13, 20)], fill=col)

        # 5. LIGHT RAIN / DRIZZLE
        elif code in [176, 263, 266, 293, 296, 353]:
            if is_night:
                draw.ellipse([9, 9, 14, 14], fill=(150, 150, 160))
                draw.ellipse([11, 8, 16, 12], fill=(0, 0, 0))
            draw.ellipse([3, 12, 12, 18], fill=(60, 60, 80) if is_night else (100, 100, 130))
            draw.point([(6, 20), (10, 21)], fill=(0, 150, 255))

        # 6. HEAVY RAIN
        elif code in [299, 302, 305, 308, 356, 359]:
            if is_night:
                draw.ellipse([9, 8, 13, 12], fill=(100, 100, 110))
                draw.ellipse([11, 7, 15, 11], fill=(0, 0, 0))
            draw.ellipse([3, 12, 12, 18], fill=(40, 40, 55) if is_night else (70, 70, 90))
            for x in [5, 8, 11]: draw.line([(x, 20), (x-1, 23)], fill=(0, 120, 255))

        # 7. SNOW
        elif code in [179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371]:
            if is_night:
                draw.ellipse([6, 10, 10, 14], fill=(60, 60, 80))
            draw.point([(8, 12), (4, 15), (12, 15), (8, 18), (4, 21), (12, 21), (8, 24)], fill=(255, 255, 255))

        # 8. SLEET / ICE PELLETS
        elif code in [182, 185, 281, 284, 311, 314, 317, 320, 350, 362, 365, 374, 377]:
            if is_night:
                draw.ellipse([8, 9, 12, 13], fill=(100, 100, 120))
            draw.ellipse([4, 12, 11, 17], fill=(120, 120, 150) if is_night else (150, 150, 180))
            draw.point([(6, 19), (10, 20)], fill=(180, 180, 230))
            draw.point([(8, 22)], fill=(0, 150, 255))

        # 9. THUNDER
        elif code in [200, 386, 389, 392, 395]:
            draw.ellipse([3, 12, 12, 18], fill=(30, 30, 40) if is_night else (60, 60, 70))
            draw.line([(8, 19), (6, 22), (10, 22), (8, 26)], fill=(255, 255, 0))
        
        else: # Default
            draw.ellipse([3, 14, 13, 20], fill=(100, 100, 100) if is_night else (120, 120, 120))

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
