import asyncio
import time
from PIL import Image, ImageDraw, ImageFont
import pypixelcolor
import os

# Configuration
DEVICE_MAC = "95:0B:57:BF:8F:8D"

class WeatherPreview:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = pypixelcolor.Client(mac_address)
        self.is_connected = False

    def connect(self):
        print(f"Connecting to {self.mac_address}...")
        try:
            self.client.connect()
            self.is_connected = True
            print("Connected!")
        except Exception as e:
            print(f"Connection failed: {e}")

    def draw_weather_pictogram(self, draw, code, is_night=False):
        """Draws a highly granular 16x32 weather pictogram on the left side."""
        # 1. SUNNY / CLEAR
        if code == 113: 
            if is_night:
                draw.ellipse([4, 12, 12, 20], fill=(240, 240, 240))
                draw.ellipse([7, 10, 15, 18], fill=(0, 0, 0))
            else:
                draw.ellipse([5, 13, 11, 19], fill=(255, 200, 0))
                draw.point([(8, 11), (8, 21), (3, 16), (13, 16)], fill=(255, 180, 0))
                draw.point([(5, 13), (11, 13), (5, 19), (11, 19)], fill=(255, 150, 0))

        # 2. PARTLY CLOUDY
        elif code == 116:
            if is_night:
                draw.ellipse([7, 11, 13, 17], fill=(200, 200, 200))
                draw.ellipse([9, 10, 15, 15], fill=(0, 0, 0))
            else:
                draw.ellipse([8, 11, 13, 16], fill=(255, 200, 0))
            draw.ellipse([3, 15, 10, 21], fill=(120, 120, 130) if is_night else (180, 180, 180))
            draw.ellipse([6, 14, 13, 19], fill=(80, 80, 90) if is_night else (140, 140, 150))

        # 3. CLOUDY / OVERCAST
        elif code in [119, 122]:
            if is_night:
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
        elif code in [176, 263, 296, 353]:
            if is_night:
                draw.ellipse([9, 9, 14, 14], fill=(150, 150, 160))
                draw.ellipse([11, 8, 16, 12], fill=(0, 0, 0))
            draw.ellipse([3, 12, 12, 18], fill=(60, 60, 80) if is_night else (100, 100, 130))
            draw.point([(6, 20), (10, 21)], fill=(0, 150, 255))

        # 6. HEAVY RAIN
        elif code in [302, 308, 359]:
            if is_night:
                draw.ellipse([9, 8, 13, 12], fill=(100, 100, 110))
                draw.ellipse([11, 7, 15, 11], fill=(0, 0, 0))
            draw.ellipse([3, 12, 12, 18], fill=(40, 40, 55) if is_night else (70, 70, 90))
            for x in [5, 8, 11]: draw.line([(x, 20), (x-1, 23)], fill=(0, 120, 255))

        # 7. SNOW
        elif code in [332, 338]:
            if is_night:
                draw.ellipse([6, 10, 10, 14], fill=(60, 60, 80))
            draw.point([(8, 12), (4, 15), (12, 15), (8, 18), (4, 21), (12, 21), (8, 24)], fill=(255, 255, 255))

        # 8. SLEET / ICE
        elif code in [317, 350]:
            if is_night:
                draw.ellipse([8, 9, 12, 13], fill=(100, 100, 120))
            draw.ellipse([4, 12, 11, 17], fill=(120, 120, 150) if is_night else (150, 150, 180))
            draw.point([(6, 19), (10, 20)], fill=(180, 180, 230)) 
            draw.point([(8, 22)], fill=(0, 150, 255)) 

        # 9. THUNDER
        elif code in [389]:
            draw.ellipse([3, 12, 12, 18], fill=(30, 30, 40) if is_night else (60, 60, 70))
            draw.line([(8, 19), (6, 22), (10, 22), (8, 26)], fill=(255, 255, 0))

    def preview(self):
        self.connect()
        if not self.is_connected: return

        # Load font
        try:
            font_path = os.path.join(pypixelcolor.__path__[0], 'fonts', 'VCR_OSD_MONO.ttf')
            font = ImageFont.truetype(font_path, 10)
        except:
            font = ImageFont.load_default()

        # Full day/night showcase
        scenarios = [
            # Day icons
            (113, False, "SUNNY"),
            (116, False, "P.CLOUD"),
            (119, False, "CLOUDY"),
            (248, False, "FOGGY"),
            (296, False, "L.RAIN"),
            (308, False, "H.RAIN"),
            (332, False, "SNOW"),
            (317, False, "SLEET"),
            (389, False, "STORM"),
            # Night icons
            (113, True, "MOON"),
            (116, True, "N.CLOUD"),
            (119, True, "N.COVER"),
            (296, True, "N.RAIN"),
            (332, True, "N.SNOW"),
        ]

        print("Starting icon preview cycle...")
        try:
            for code, night, name in scenarios:
                img = Image.new('RGB', (32, 32), (0, 0, 0))
                draw = ImageDraw.Draw(img)
                self.draw_weather_pictogram(draw, code, night)
                
                # Add label
                draw.text((16, 11), name, font=font, fill=(255, 255, 255))
                
                img.save("preview.png")
                self.client.send_image("preview.png")
                print(f"Displaying: {name}")
                time.sleep(2.5)
        finally:
            self.client.disconnect()
            if os.path.exists("preview.png"): os.remove("preview.png")

if __name__ == "__main__":
    WeatherPreview(DEVICE_MAC).preview()
