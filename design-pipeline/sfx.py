"""Sound effects, synthesised (no third-party audio): app-assets/sfx/*.wav, 16-bit mono 44.1 kHz.

  pop.wav   green character hit: a bubbly pop (falling pitch + a little noise)
  bonk.wav  red/yellow character tapped: a soft low boing
  click.wav UI button
  end.wav   round over: three rising notes
"""
import wave
import numpy as np
from paths import asset_dir

SR = 44100
OUT = asset_dir('sfx')
rng = np.random.default_rng(5)


def t_(dur):
    return np.arange(int(SR * dur)) / SR


def env(t, attack, decay):
    return np.minimum(t / attack, 1.0) * np.exp(-t / decay)


def sweep(f0, f1, dur, shape='sine'):
    t = t_(dur)
    f = f0 * (f1 / f0) ** (t / dur)                     # exponential glide
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) if shape == 'sine' else 2 / np.pi * np.arcsin(np.sin(ph))


def save(name, x, gain=0.8):
    x = x / (np.abs(x).max() + 1e-9) * gain
    fade = min(len(x), int(SR * 0.004))
    x[-fade:] *= np.linspace(1, 0, fade)
    with wave.open(f'{OUT}/{name}.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype('<i2').tobytes())


d = 0.13
t = t_(d)
pop = sweep(1100, 280, d) * env(t, 0.002, 0.035)
pop += 0.35 * sweep(2200, 560, d) * env(t, 0.001, 0.02)
pop += 0.25 * rng.normal(0, 1, len(t)) * env(t, 0.0005, 0.006)
save('pop', pop)

d = 0.26
t = t_(d)
vib = 1 + 0.06 * np.sin(2 * np.pi * 18 * t)
f = 260 * (150 / 260) ** (t / d) * vib
bonk = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(t, 0.004, 0.09)
bonk += 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR) * env(t, 0.004, 0.05)
save('bonk', bonk, 0.7)

d = 0.035
t = t_(d)
click = sweep(1800, 900, d) * env(t, 0.0008, 0.008)
save('click', click, 0.6)

notes = [523.25, 659.25, 783.99, 1046.5]
parts = []
for i, fr in enumerate(notes):
    dur = 0.11 if i < len(notes) - 1 else 0.38
    tt = t_(dur)
    parts.append((sweep(fr, fr, dur, 'tri') + 0.3 * sweep(fr * 2, fr * 2, dur)) * env(tt, 0.004, 0.08 if i < len(notes) - 1 else 0.16))
save('end', np.concatenate(parts), 0.7)
print('written', OUT)
