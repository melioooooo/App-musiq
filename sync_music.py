import asyncio
import io
import time
import os
import requests
from PIL import Image, ImageDraw, ImageFont
import pypixelcolor
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager, GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
from winrt.windows.storage.streams import DataReader, Buffer
from dotenv import load_dotenv

# Load configuration
load_dotenv()
DEVICE_MAC = os.getenv("DEVICE_MAC", "95:0B:57:BF:8F:8D")
LOCATION = os.getenv("LOCATION", "Strasbourg")

CHECK_INTERVAL = 1  # Seconds between checks
MUSIC_DURATION = 25  # Default music duration
CLOCK_DURATION = 5   # Seconds to show clock

class MusicSyncApp:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = pypixelcolor.Client(mac_address)
        self.current_track_id = None
        self.current_track_name = None
        self.current_thumbnail_ref = None
        self.is_connected = False
        self.is_paused = False
        
        # Weather tracking
        self.last_weather = None
        self.last_weather_fetch = 0
        
        # Tracking which parts of the song we've shown the title for
        self.shown_phases = set() # "START", "MIDDLE", "END"

    async def connect(self):
        print(f"Connecting to LED panel at {self.mac_address}...")
        try:
            self.client.connect()
            self.is_connected = True
            print("Connected successfully!")
        except Exception as e:
            print(f"Failed to connect: {e}")
            self.is_connected = False

    def fetch_weather(self):
        """Fetches weather once an hour from wttr.in with retry backoff."""
        now = time.time()
        
        # If we have weather and it's less than an hour old, keep it
        if self.last_weather and (now - self.last_weather_fetch < 3600):
            return self.last_weather
            
        # If the last attempt failed (or we have none), wait at least 5 minutes before retrying
        if (now - self.last_weather_fetch < 300):
            return self.last_weather

        print(f"Fetching current weather for {LOCATION}...")
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
        except Exception as e:
            print(f"Weather fetch failed (will retry in 5m): {e}")

        # Mark attempt time on failure to trigger 5m backoff
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
                # Very faint moon glow behind fog
                draw.ellipse([8, 11, 12, 15], fill=(60, 60, 70))
            col = (80, 80, 100) if is_night else (180, 180, 200)
            draw.line([(4, 14), (12, 14)], fill=col)
            draw.line([(3, 17), (11, 17)], fill=col)
            draw.line([(5, 20), (13, 20)], fill=col)

        # 5. LIGHT RAIN / DRIZZLE
        elif code in [176, 263, 266, 293, 296, 353]:
            if is_night:
                # Small moon behind rain cloud
                draw.ellipse([9, 9, 14, 14], fill=(150, 150, 160))
                draw.ellipse([11, 8, 16, 12], fill=(0, 0, 0))
            draw.ellipse([3, 12, 12, 18], fill=(60, 60, 80) if is_night else (100, 100, 130))
            draw.point([(6, 20), (10, 21)], fill=(0, 150, 255))

        # 6. HEAVY RAIN
        elif code in [299, 302, 305, 308, 356, 359]:
            if is_night:
                # Tiny moon behind storm cloud
                draw.ellipse([9, 8, 13, 12], fill=(100, 100, 110))
                draw.ellipse([11, 7, 15, 11], fill=(0, 0, 0))
            draw.ellipse([3, 12, 12, 18], fill=(40, 40, 55) if is_night else (70, 70, 90))
            for x in [5, 8, 11]: draw.line([(x, 20), (x-1, 23)], fill=(0, 120, 255))

        # 7. SNOW
        elif code in [179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371]:
            if is_night:
                # Soft glow behind snow
                draw.ellipse([6, 10, 10, 14], fill=(60, 60, 80))
            draw.point([(8, 12), (4, 15), (12, 15), (8, 18), (4, 21), (12, 21), (8, 24)], fill=(255, 255, 255))

        # 8. SLEET / ICE PELLETS
        elif code in [182, 185, 281, 284, 311, 314, 317, 320, 350, 362, 365, 374, 377]:
            if is_night:
                draw.ellipse([8, 9, 12, 13], fill=(100, 100, 120))
            draw.ellipse([4, 12, 11, 17], fill=(120, 120, 150) if is_night else (150, 150, 180))
            draw.point([(6, 19), (10, 20)], fill=(180, 180, 230)) # Ice
            draw.point([(8, 22)], fill=(0, 150, 255)) # Rain

        # 9. THUNDER
        elif code in [200, 386, 389, 392, 395]:
            draw.ellipse([3, 12, 12, 18], fill=(30, 30, 40) if is_night else (60, 60, 70))
            draw.line([(8, 19), (6, 22), (10, 22), (8, 26)], fill=(255, 255, 0))
        
        else: # Default
            draw.ellipse([3, 14, 13, 20], fill=(100, 100, 100) if is_night else (120, 120, 120))

    async def get_current_media_info(self):
        try:
            sessions = await SessionManager.request_async()
            current_session = sessions.get_current_session()
            if not current_session:
                return None, None, PlaybackStatus.CLOSED, None, 0, 0

            properties = await current_session.try_get_media_properties_async()
            playback_info = current_session.get_playback_info()
            timeline = current_session.get_timeline_properties()
            
            status = playback_info.playback_status
            duration = timeline.end_time.total_seconds()
            position = timeline.position.total_seconds()

            if not properties:
                return None, None, status, None, position, duration

            # Create a unique ID for the track to avoid redundant updates
            track_id = f"{properties.artist} - {properties.title}"
            return track_id, properties.thumbnail, status, properties.title, position, duration
        except Exception as e:
            # print(f"Error getting media info: {e}")
            return None, None, PlaybackStatus.CLOSED, None, 0, 0

    async def process_and_send_thumbnail(self, thumbnail_stream_ref):
        if not thumbnail_stream_ref:
            return

        try:
            # Open the stream
            stream = await thumbnail_stream_ref.open_read_async()
            size = stream.size
            if size == 0:
                print("Thumbnail stream is empty.")
                return
            
            reader = DataReader(stream)
            await reader.load_async(size)
            
            data = bytearray(size)
            reader.read_bytes(data)
            
            # Process with Pillow
            img = Image.open(io.BytesIO(data))
            
            # Save to temporary file
            temp_path = "current_album.png"
            img.save(temp_path)
            
            print(f"Sending album cover to panel...")
            self.client.send_image(temp_path, resize_method='crop')
            print("Update sent!")
            
        except Exception as e:
            print(f"Error processing thumbnail: {e}")

    def show_custom_clock(self, color="ffffff"):
        """Generates and sends a split weather/clock image (Weather on left, Vertical Clock on right)."""
        # 1. Fetch data
        weather_code = self.fetch_weather()
        h = time.strftime("%H")
        m = time.strftime("%M")
        
        # 2. Setup drawing
        img = Image.new('RGB', (32, 32), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 3. Draw Weather on Left (0-15)
        self.draw_weather_pictogram(draw, weather_code)
        
        # 4. Draw Clock on Right (16-31)
        try:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            text_color = (r, g, b)
        except:
            text_color = (255, 255, 255)

        try:
            font_path = os.path.join(pypixelcolor.__path__[0], 'fonts', 'VCR_OSD_MONO.ttf')
            font = ImageFont.truetype(font_path, 15)
        except:
            font = ImageFont.load_default()

        try:
            h_bbox = draw.textbbox((0, 0), h, font=font)
            m_bbox = draw.textbbox((0, 0), m, font=font)
            h_w = h_bbox[2] - h_bbox[0]
            m_w = m_bbox[2] - m_bbox[0]
            
            # Position inside right half (16-30 to leave 1px border on right)
            # Center of right half is x = 16 + (15 - width) // 2
            # Shifting minutes up to 15 to reduce the gap
            draw.text(((16 + (15 - h_w) // 2), 2), h, font=font, fill=text_color)
            draw.text(((16 + (15 - m_w) // 2), 15), m, font=font, fill=text_color)
        except:
            draw.text((18, 2), h, fill=text_color)
            draw.text((18, 17), m, fill=text_color)
        
        temp_path = "clock_weather.png"
        img.save(temp_path)
        
        print(f"Showing weather clock: {h}/{m} (Weather: {weather_code}, Color: #{color})")
        try:
            self.client.send_image(temp_path)
        except Exception as e:
            print(f"Failed to show weather clock: {e}")

    def calculate_text_duration(self, text):
        return max(10, len(text) * 0.35 + 3)

    async def run(self):
        await self.connect()
        if not self.is_connected:
            return

        print("Monitoring music playback... Press Ctrl+C to stop.")
        
        last_switch_time = time.time()
        current_title_duration = 5
        mode = "TITLE"
        
        try:
            while True:
                current_time = time.time()
                
                # 1. Check for track changes and playback status
                track_id, thumbnail_ref, status, track_name, position, duration = await self.get_current_media_info()
                is_playing = (status == PlaybackStatus.PLAYING)
                
                # Update track if changed
                if track_id and track_id != self.current_track_id:
                    print(f"Track Change Detected: {track_id}")
                    self.current_track_id = track_id
                    self.current_track_name = track_name
                    self.current_thumbnail_ref = thumbnail_ref
                    self.shown_phases = {"START"} # Reset phases for new track
                    
                    # Update local color and art immediately
                    await self.process_and_send_thumbnail(thumbnail_ref)
                    
                    if is_playing:
                        print(f"Showing Title (Start): {track_name}")
                        try:
                            self.client.send_text(track_name, animation=1, speed=100)
                        except: pass
                        mode = "TITLE"
                        current_title_duration = self.calculate_text_duration(track_name)
                        last_switch_time = current_time
                
                # 2. Handle 3-Point Triggers (Middle and End)
                if is_playing and track_id and duration > 0:
                    progress = position / duration
                    
                    # Middle Trigger (approx 50%)
                    if 0.48 < progress < 0.52 and "MIDDLE" not in self.shown_phases:
                        print(f"Showing Title (Middle): {track_name}")
                        self.shown_phases.add("MIDDLE")
                        try: self.client.send_text(track_name, animation=1, speed=100)
                        except: pass
                        mode = "TITLE"
                        current_title_duration = self.calculate_text_duration(track_name)
                        last_switch_time = current_time
                        
                    # End Trigger (approx 90%)
                    if progress > 0.90 and "END" not in self.shown_phases:
                        print(f"Showing Title (End): {track_name}")
                        self.shown_phases.add("END")
                        try: self.client.send_text(track_name, animation=1, speed=100)
                        except: pass
                        mode = "TITLE"
                        current_title_duration = self.calculate_text_duration(track_name)
                        last_switch_time = current_time

                # 3. Handle Idle/Pause Logic
                if not is_playing:
                    if not self.is_paused:
                        print("Music Paused/Idle: Switching to Custom Clock Mode...")
                        self.is_paused = True
                        self.show_custom_clock()
                        last_switch_time = current_time
                    elif current_time - last_switch_time >= 30:
                        # Periodically refresh clock while idle to keep time accurate
                        self.show_custom_clock()
                        last_switch_time = current_time
                
                elif is_playing and self.is_paused:
                    print("Music Resumed: Showing title...")
                    self.is_paused = False
                    if self.current_track_name:
                        try: self.client.send_text(self.current_track_name, animation=1, speed=100)
                        except: pass
                    mode = "TITLE"
                    current_title_duration = self.calculate_text_duration(self.current_track_name)
                    last_switch_time = current_time

                # 4. Handle Rotation State Machine (only if playing)
                if is_playing:
                    if mode == "TITLE":
                        if current_time - last_switch_time >= current_title_duration:
                            print("Rotation: Switching to Music Art...")
                            if self.current_thumbnail_ref:
                                await self.process_and_send_thumbnail(self.current_thumbnail_ref)
                            mode = "MUSIC"
                            last_switch_time = current_time
                    
                    elif mode == "MUSIC":
                        if current_time - last_switch_time >= MUSIC_DURATION:
                            print(f"Rotation: Switching to Custom Clock for 5s...")
                            self.show_custom_clock()
                            mode = "CLOCK"
                            last_switch_time = current_time
                    
                    elif mode == "CLOCK":
                        # If in clock mode during playback, update every minute to keep time accurate
                        # (Though for a 5s window, it's not strictly necessary)
                        if current_time - last_switch_time >= CLOCK_DURATION:
                            print("Rotation: Music Mode...")
                            if self.current_thumbnail_ref:
                                await self.process_and_send_thumbnail(self.current_thumbnail_ref)
                            mode = "MUSIC"
                            last_switch_time = current_time
                
                await asyncio.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            if self.is_connected:
                # Neutral state: white clock
                self.show_custom_clock("ffffff")
                self.client.disconnect()

if __name__ == "__main__":
    app = MusicSyncApp(DEVICE_MAC)
    asyncio.run(app.run())
