import pypixelcolor
from PIL import Image
import os
from dotenv import load_dotenv

# Configuration
load_dotenv()
DEVICE_MAC = os.getenv("DEVICE_MAC", "95:0B:57:BF:8F:8D")

def turn_off_panel():
    print(f"Connecting to {DEVICE_MAC} to turn off...")
    client = pypixelcolor.Client(DEVICE_MAC)
    try:
        client.connect()
        
        # Create a 32x32 black image
        black_img = Image.new('RGB', (32, 32), color=(0, 0, 0))
        temp_path = "black_screen.png"
        black_img.save(temp_path)
        
        print("Sending black screen...")
        client.send_image(temp_path)
        
        # Optionally, we could try to just set black text if that's preferred
        # or use save_slot if we wanted to persist this.
        
        print("Panel turned off (black).")
    except Exception as e:
        print(f"Failed to turn off panel: {e}")
    finally:
        client.disconnect()
        if os.path.exists("black_screen.png"):
            os.remove("black_screen.png")

if __name__ == "__main__":
    turn_off_panel()
