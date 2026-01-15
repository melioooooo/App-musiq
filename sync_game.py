import os
import time
import asyncio
import win32gui
import win32process
import win32api
import win32con
from PIL import Image, ImageWin
import pypixelcolor
from dotenv import load_dotenv

# Configuration
load_dotenv()
DEVICE_MAC = os.getenv("DEVICE_MAC", "95:0B:57:BF:8F:8D")
CHECK_INTERVAL = 2  # Seconds between window checks

class GameSyncApp:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = pypixelcolor.Client(mac_address)
        self.is_connected = False
        self.last_exe_path = None

    async def connect(self):
        print(f"Connecting to LED panel at {self.mac_address}...")
        try:
            self.client.connect()
            self.is_connected = True
            print("Connected successfully!")
        except Exception as e:
            print(f"Failed to connect: {e}")
            self.is_connected = False

    def get_foreground_exe(self):
        """Returns the full path to the executable of the active window."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            return exe_path
        except Exception:
            return None

    def extract_icon(self, exe_path, output_path="game_icon.png"):
        """Extracts the icon from an EXE and saves it as a 32x32 PNG."""
        try:
            # Get small and large icons
            # We want the large one for better resizing results
            large, small = win32gui.ExtractIconEx(exe_path, 0)
            
            if not large:
                return False
            
            # Use the first large icon
            hicon = large[0]
            
            # Destroy small icons and other large icons
            for h in small: win32gui.DestroyIcon(h)
            for h in large[1:]: win32gui.DestroyIcon(h)
            
            import win32ui
            
            # Create a device context
            hdc = win32gui.GetDC(0)
            hdc_mem = win32gui.CreateCompatibleDC(hdc)
            hbmp = win32gui.CreateCompatibleBitmap(hdc, 32, 32)
            hold_bmp = win32gui.SelectObject(hdc_mem, hbmp)
            
            # Draw the icon into the memory DC
            win32gui.DrawIconEx(hdc_mem, 0, 0, hicon, 32, 32, 0, None, win32con.DI_NORMAL)
            
            # Use win32ui to save the bitmap to a file
            # This is the most reliable way to bridge Windows icons to PIL
            cdc = win32ui.CreateDCFromHandle(hdc_mem)
            bmp = win32ui.CreateBitmapFromHandle(hbmp)
            temp_bmp = "temp_capture.bmp"
            bmp.SaveBitmapFile(cdc, temp_bmp)
            
            # Cleanup Windows handles
            win32gui.SelectObject(hdc_mem, hold_bmp)
            win32gui.DeleteDC(hdc_mem)
            win32gui.ReleaseDC(0, hdc)
            win32gui.DestroyIcon(hicon)
            win32gui.DeleteObject(hbmp)
            
            # Open with PIL
            img = Image.open(temp_bmp)
            img = img.convert("RGBA")
            if os.path.exists(temp_bmp):
                os.remove(temp_bmp)
            
            # Final touch with PIL
            img = img.resize((32, 32), Image.Resampling.LANCZOS)
            
            # Background should be black for LED panel
            bg = Image.new("RGB", (32, 32), (0, 0, 0))
            bg.paste(img, (0, 0), img)
            bg.save(output_path)
            
            return True
        except Exception as e:
            print(f"Icon extraction failed: {e}")
            return False

    async def run(self):
        await self.connect()
        if not self.is_connected:
            return

        print("Monitoring active games/apps... Press Ctrl+C to stop.")
        
        try:
            while True:
                exe_path = self.get_foreground_exe()
                
                # Basic filter: ignore system apps
                if exe_path and "explorer.exe" not in exe_path.lower() and "TextInputHost.exe" not in exe_path:
                    
                    if exe_path != self.last_exe_path:
                        app_name = os.path.basename(exe_path)
                        print(f"Detected Active App: {app_name}")
                        
                        if self.extract_icon(exe_path):
                            print(f"Sending icon to panel...")
                            self.client.send_image("game_icon.png", resize_method='crop')
                            self.last_exe_path = exe_path
                
                await asyncio.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            if self.is_connected:
                self.client.disconnect()

if __name__ == "__main__":
    app = GameSyncApp(DEVICE_MAC)
    asyncio.run(app.run())
