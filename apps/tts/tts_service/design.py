"""Designs a character's voice from a text description (Qwen3-TTS VoiceDesign).

    make voice CHARACTER=mimi          # 3 candidates in characters/mimi/voice-candidates/
    make voice CHARACTER=mimi PICK=2   # use candidate 2 as the character's voice

characters/<id>/voice.yaml:
    description: "A confident young adult woman's voice, sarcastic and teasing..."
    text: "A line in the character's language and style, ~10 seconds long."

The chosen clip becomes voice.wav (+ its transcript voice.txt), which the TTS service
clones for every reply. Uses Qwen3-TTS 1.7B VoiceDesign through qwentts.cpp (8-bit); stop
the TTS service and free the chat model first if the GPU is short on memory.
"""

import argparse
import shutil
import sys
from pathlib import Path

import soundfile as sf
import yaml

from tts_service.voices import characters_dir, language_name

DESIGN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
DESIGN_QUANT = "Q8_0"
CANDIDATES = 3


def design(folder: Path) -> None:
    config = yaml.safe_load((folder / "voice.yaml").read_text(encoding="utf-8")) or {}
    description, text = config.get("description"), config.get("text")
    if not description or not text:
        sys.exit(f"{folder / 'voice.yaml'} needs 'description' and 'text'")
    character = yaml.safe_load((folder / "character.yaml").read_text(encoding="utf-8"))
    language = language_name(character.get("character", {}).get("language", "es")).lower()

    from qwentts_cpp import QwenTTS

    print(f"Loading {DESIGN_MODEL} {DESIGN_QUANT} (first run downloads it)...")
    model = QwenTTS.from_pretrained(DESIGN_MODEL, quant=DESIGN_QUANT, log_level="warning")
    out = folder / "voice-candidates"
    out.mkdir(exist_ok=True)
    for n in range(1, CANDIDATES + 1):
        audio, sr = model.synthesize(text=text.strip(), instruct=description.strip(), lang=language)
        sf.write(out / f"{n}.wav", audio, sr)
        print(f"  candidate {n}: {out / f'{n}.wav'}")
    (out / "text.txt").write_text(text.strip(), encoding="utf-8")
    if not (folder / "voice.wav").exists():
        pick(folder, 1)
    else:
        print(f"Kept the current voice. To switch: make voice CHARACTER={folder.name} PICK=<n>")


def pick(folder: Path, n: int) -> None:
    out = folder / "voice-candidates"
    shutil.copyfile(out / f"{n}.wav", folder / "voice.wav")
    shutil.copyfile(out / "text.txt", folder / "voice.txt")
    print(f"{folder.name} now uses candidate {n}. Restart the TTS service to apply it.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("character")
    parser.add_argument("--pick", type=int, help="use this candidate instead of designing")
    args = parser.parse_args()
    folder = characters_dir() / args.character
    if not folder.is_dir():
        sys.exit(f"No such character: {folder}")
    if args.pick:
        pick(folder, args.pick)
    else:
        design(folder)


if __name__ == "__main__":
    main()
