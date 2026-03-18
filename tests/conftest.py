from pathlib import Path
import sys


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

VOICE_SRC_ROOT = Path(__file__).resolve().parents[1] / "packages" / "kaivra-voice" / "src"
if str(VOICE_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(VOICE_SRC_ROOT))
