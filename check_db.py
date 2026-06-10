"""Quick end-to-end test: cut a 30s clip and convert to vertical."""
import sys, os
sys.path.insert(0, os.getcwd())

from pathlib import Path
from backend.utils.ffmpeg import cut_clip, convert_vertical

src = Path("uploads/76445fa2649d41b790208c331a8555c4.mp4")
raw = Path("temp/e2e_test_raw.mp4")
final = Path("temp/e2e_test_final.mp4")

Path("temp").mkdir(exist_ok=True)

print("Step 1: Cutting 30s clip from 5:00...")
cut_clip(src, raw, start_time=300, duration=30)
print(f"  Raw clip: {raw.stat().st_size / 1024:.0f} KB")

print("Step 2: Converting to 1080x1920 vertical...")
convert_vertical(raw, final)
print(f"  Final clip: {final.stat().st_size / 1024:.0f} KB")

print("\nSUCCESS! Pipeline is working.")

# Cleanup
raw.unlink(missing_ok=True)
final.unlink(missing_ok=True)
