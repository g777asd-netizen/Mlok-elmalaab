# -*- coding: utf-8 -*-
"""
music_bed.py — موسيقى خلفية أصلية 100% (توليد برمجي)
======================================================
الهدف: خلفية موسيقية حماسية للفيديوهات بدون أي حقوق ملكية —
الموسيقى تُولَّد بالكامل بالكود (موجات مركبة) فلا توجد أي عينة أو مقطع جاهز.

الأسلوب: إيقاع رياضي حماسي (طبول + بيس + هارموني هادئ) بسرعة 104 BPM
في سلم لا مينور: Am - F - C - G (أكورد لكل مقطع، ٤ مقاطع في اللوب).

render_music_bed(path, duration) → يكتب ملف WAV مونو 44.1kHz جاهز للدمج.
"""

import math
import wave
import numpy as np

SR = 44100
BPM = 104
BEAT = 60.0 / BPM
BAR = 4 * BEAT

# الأكوردات: (تردد الجذر بالهرتز، أبعاد الأكورد بالنصف نغمات)
# A2, F2, C3, G2 — لا مينور
PROGRESSION = [
    (110.00, (0, 3, 7)),   # Am
    (87.31, (0, 4, 7)),    # F
    (130.81, (0, 4, 7)),   # C
    (98.00, (0, 4, 7)),    # G
]

_rng = np.random.default_rng(7)


def _env_exp(n, tau):
    return np.exp(-np.arange(n) / (SR * tau))


def _kick(dur=0.22):
    n = int(SR * dur)
    t = np.arange(n) / SR
    freq = 150.0 * np.exp(-t / 0.045) + 45.0
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * _env_exp(n, 0.085)


def _clap(dur=0.14):
    n = int(SR * dur)
    noise = _rng.standard_normal(n)
    env = _env_exp(n, 0.045) * (0.6 + 0.4 * np.sin(np.arange(n) / SR * 220.0) ** 2)
    return noise * env * 0.7


def _hat(dur=0.05):
    n = int(SR * dur)
    noise = _rng.standard_normal(n)
    hp = np.diff(noise, prepend=0.0)   # تقريب فلتر تمرير عالي
    return hp * _env_exp(n, 0.018)


def _bass_note(freq, dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    wave_ = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
    wave_ = np.tanh(wave_ * 1.6)
    attack = min(int(0.008 * SR), n)
    env = np.ones(n)
    env[:attack] = np.linspace(0, 1, attack)
    release = min(int(0.06 * SR), n)
    env[-release:] *= np.linspace(1, 0.25, release)
    return wave_ * env


def _pad_chord(root, intervals, dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for iv in intervals:
        f = root * (2 ** (iv / 12.0)) * 2.0   # أوكتاف أعلى للهارموني
        for detune in (-0.0025, 0.0025):
            sig = np.zeros(n)
            for k in range(1, 6):
                sig += np.sin(2 * np.pi * f * (1 + detune) * k * t) / (k ** 1.6)
            out += sig
    attack = int(0.35 * n)
    release = int(0.30 * n)
    env = np.ones(n)
    env[:attack] = np.linspace(0, 1, attack) ** 1.5
    env[-release:] *= np.linspace(1, 0, release) ** 1.5
    return out * env / (len(intervals) * 2)


def _place(buf, sig, start_s, gain):
    i0 = int(start_s * SR)
    i1 = min(i0 + len(sig), len(buf))
    if i1 > i0:
        buf[i0:i1] += sig[: i1 - i0] * gain


def render_music_bed(path, duration, sr=SR):
    """توليد الخلفية الموسيقية بطول duration ثانية وحفظها كـ WAV"""
    duration = max(5.0, float(duration))
    n = int(sr * duration)
    mix = np.zeros(n)

    kick = _kick()
    clap = _clap()
    hat = _hat()

    loop_dur = BAR * len(PROGRESSION)
    n_bars = int(math.ceil(duration / BAR))

    for bar_idx in range(n_bars):
        root, intervals = PROGRESSION[bar_idx % len(PROGRESSION)]
        bar_start = bar_idx * BAR

        # الهارموني: أربع دقات
        _place(mix, _pad_chord(root, intervals, BAR), bar_start, 0.42)

        for beat in range(4):
            beat_start = bar_start + beat * BEAT
            _place(mix, kick, beat_start, 0.55)                    # طبلة على كل دقة
            if beat in (1, 3):
                _place(mix, clap, beat_start, 0.16)                # تصفيقة على ٢ و ٤
            for eighth in range(2):
                e_start = beat_start + eighth * BEAT / 2
                bass_dur = BEAT / 2 * 0.9
                _place(mix, _bass_note(root, bass_dur), e_start, 0.34)
            _place(mix, hat, beat_start + BEAT / 2, 0.05)          # هات على النصف الثاني

    # تنعيم بسيط ومنع القص
    mix = np.tanh(mix * 1.1)
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.82

    # فيد إن/أوت
    fade_in = int(0.4 * sr)
    fade_out = int(min(2.5, duration / 4) * sr)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)

    pcm = (mix * 32767).astype('<i2')
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    print(f"🎵 موسيقى خلفية أصلية جاهزة ({duration:.1f}ث): {path}")
    return path
