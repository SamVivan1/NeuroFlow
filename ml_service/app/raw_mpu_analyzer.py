import math
from typing import Optional

import numpy as np

from app.schemas import RawMpuSample


def infer_sampling_rate(samples: list[RawMpuSample], fallback: Optional[float]) -> float:
    if fallback is not None and fallback > 0:
        return float(fallback)

    timestamps = [
        float(s.timestamp)
        for s in samples
        if s.timestamp is not None
    ]

    if len(timestamps) < 3:
        return 50.0

    diffs = np.diff(np.asarray(timestamps, dtype=np.float64))

    diffs = diffs[diffs > 0]

    if diffs.size == 0:
        return 50.0

    median_diff = float(np.median(diffs))

    # Jika timestamp dalam millisecond.
    if median_diff > 1.0:
        median_diff = median_diff / 1000.0

    if median_diff <= 0:
        return 50.0

    return float(1.0 / median_diff)


def magnitude(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    return np.sqrt((x * x) + (y * y) + (z * z))


def detrend(signal: np.ndarray) -> np.ndarray:
    return signal - np.mean(signal)


def band_energy(signal: np.ndarray, fs: float, low: float, high: float) -> float:
    signal = detrend(signal.astype(np.float64))

    if signal.size < 8:
        return 0.0

    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / fs)

    mask = (freqs >= low) & (freqs <= high)

    if not np.any(mask):
        return 0.0

    return float(np.sum(power[mask]))


def dominant_frequency(signal: np.ndarray, fs: float, low: float = 0.5, high: float = 15.0) -> float:
    signal = detrend(signal.astype(np.float64))

    if signal.size < 8:
        return 0.0

    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / fs)

    mask = (freqs >= low) & (freqs <= high)

    if not np.any(mask):
        return 0.0

    selected_freqs = freqs[mask]
    selected_power = power[mask]

    return float(selected_freqs[np.argmax(selected_power)])


def classify_intensity(acc_rms: float, gyro_rms: float, ratio_3_8: float) -> str:
    """
    Threshold awal berbasis heuristik.
    Nanti wajib dikalibrasi dari data real NeuroFlow.
    """

    combined = (acc_rms * 0.65) + (gyro_rms * 0.35)

    if ratio_3_8 < 0.15 or combined < 0.03:
        return "Normal"

    if combined < 0.08:
        return "Ringan"

    if combined < 0.18:
        return "Sedang"

    return "Parah"


def classify_pattern(
    dominant_hz: float,
    ratio_4_6: float,
    ratio_8_12: float,
    intensity: str,
) -> tuple[str, str]:
    """
    Klasifikasi pola tremor dari MPU saja.
    Tidak mengklaim stress final tanpa HR/HRV.
    """

    if intensity == "Normal":
        return (
            "Normal / Low Motion",
            "Tidak ada pola tremor bermakna pada window ini.",
        )

    if 4.0 <= dominant_hz <= 6.5 and ratio_4_6 >= 0.20:
        return (
            "Possible Parkinson-band Tremor",
            "Energi dominan berada pada rentang 4–6 Hz. Ini konsisten dengan pola tremor Parkinson-band, tetapi bukan diagnosis final.",
        )

    if 8.0 <= dominant_hz <= 12.5 and ratio_8_12 >= 0.20:
        return (
            "High-frequency Physiologic-like Tremor",
            "Frekuensi dominan tinggi. Pola ini dapat sesuai dengan enhanced physiologic tremor, tetapi penyebab stress perlu dikonfirmasi dengan HR/HRV.",
        )

    return (
        "Mixed / Uncertain Tremor",
        "Pola tremor terdeteksi, tetapi tidak cukup spesifik untuk membedakan Parkinson-band atau physiologic-like tremor.",
    )


def analyze_raw_mpu(samples: list[RawMpuSample], sampling_rate_hz: Optional[float]):
    if len(samples) < 50:
        raise ValueError("Minimal butuh 50 sample. Untuk hasil stabil, gunakan window 4 detik pada 50–100 Hz.")

    fs = infer_sampling_rate(samples, sampling_rate_hz)

    if fs < 20:
        raise ValueError(f"Sampling rate terlalu rendah: {fs:.2f} Hz. Minimal disarankan 50 Hz.")

    ax = np.asarray([s.ax for s in samples], dtype=np.float64)
    ay = np.asarray([s.ay for s in samples], dtype=np.float64)
    az = np.asarray([s.az for s in samples], dtype=np.float64)

    gx = np.asarray([s.gx for s in samples], dtype=np.float64)
    gy = np.asarray([s.gy for s in samples], dtype=np.float64)
    gz = np.asarray([s.gz for s in samples], dtype=np.float64)

    acc_mag = magnitude(ax, ay, az)
    gyro_mag = magnitude(gx, gy, gz)

    acc_signal = detrend(acc_mag)
    gyro_signal = detrend(gyro_mag)

    total_energy = band_energy(acc_signal, fs, 0.5, 15.0)
    energy_0_3 = band_energy(acc_signal, fs, 0.5, 3.0)
    energy_3_8 = band_energy(acc_signal, fs, 3.0, 8.0)
    energy_4_6 = band_energy(acc_signal, fs, 4.0, 6.0)
    energy_8_12 = band_energy(acc_signal, fs, 8.0, 12.0)

    eps = 1e-8

    ratio_3_8 = energy_3_8 / (total_energy + eps)
    ratio_4_6 = energy_4_6 / (total_energy + eps)
    ratio_8_12 = energy_8_12 / (total_energy + eps)

    acc_rms = float(math.sqrt(np.mean(acc_signal ** 2)))
    gyro_rms = float(math.sqrt(np.mean(gyro_signal ** 2)))

    dom_hz = dominant_frequency(acc_signal, fs)

    intensity = classify_intensity(acc_rms, gyro_rms, ratio_3_8)

    pattern, stress_note = classify_pattern(
        dominant_hz=dom_hz,
        ratio_4_6=ratio_4_6,
        ratio_8_12=ratio_8_12,
        intensity=intensity,
    )

    duration_sec = len(samples) / fs

    return {
        "sample_count": len(samples),
        "sampling_rate_hz": fs,
        "window_duration_sec": duration_sec,
        "dominant_frequency_hz": dom_hz,
        "acc_rms": acc_rms,
        "gyro_rms": gyro_rms,
        "energy_0_3hz": energy_0_3,
        "energy_3_8hz": energy_3_8,
        "energy_4_6hz": energy_4_6,
        "energy_8_12hz": energy_8_12,
        "ratio_4_6_to_total": ratio_4_6,
        "ratio_8_12_to_total": ratio_8_12,
        "tremor_intensity": intensity,
        "tremor_pattern": pattern,
        "stress_interpretation": stress_note,
    }
