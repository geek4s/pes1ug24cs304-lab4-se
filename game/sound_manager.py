import math
from array import array

import pygame

# Task 3: one distinct pitch per pad, indexed by color_id.
# Red = E4, Blue = C4, Green = G4, Yellow = C5 (a C-major chord, so any order sounds musical).
PAD_FREQUENCIES = [329.63, 261.63, 392.00, 523.25]
ERROR_FREQUENCY = 110.0

TONE_LENGTH_MS = 1000   # longer than the slowest flash; tones are cut short with a fade
FADE_OUT_MS = 40


class SoundManager:
    """Synthesises the pad tones in memory, so the game needs no audio files."""

    def __init__(self, volume=0.35):
        self.enabled = False
        self.tones = []
        self.error_tone = None

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            sample_rate, sample_format, channels = pygame.mixer.get_init()
            if sample_format != -16:
                return  # tones below are built as signed 16-bit samples

            for freq in PAD_FREQUENCIES:
                self.tones.append(self._build_tone(freq, TONE_LENGTH_MS, sample_rate, channels, volume))
            self.error_tone = self._build_tone(ERROR_FREQUENCY, 500, sample_rate, channels, volume, square=True)
            self.enabled = True
        except (pygame.error, NotImplementedError):
            # No audio device available: the game stays playable, just silent.
            self.tones = []
            self.error_tone = None

    def _build_tone(self, freq, length_ms, sample_rate, channels, volume, square=False):
        total = int(sample_rate * length_ms / 1000)
        ramp = int(sample_rate * 0.008)  # 8 ms fade in/out so tones do not click
        peak = 32767 * volume
        samples = array("h")

        for i in range(total):
            value = math.sin(2 * math.pi * freq * i / sample_rate)
            if square:
                value = 0.6 if value >= 0 else -0.6
            envelope = min(1.0, i / ramp, (total - 1 - i) / ramp)
            sample = int(peak * value * envelope)
            for _ in range(channels):
                samples.append(sample)

        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, color_id):
        if not self.enabled:
            return
        self.tones[color_id].stop()
        self.tones[color_id].play()

    def stop(self, color_id):
        if not self.enabled:
            return
        self.tones[color_id].fadeout(FADE_OUT_MS)

    def play_error(self):
        if not self.enabled:
            return
        for tone in self.tones:
            tone.stop()
        self.error_tone.play()
