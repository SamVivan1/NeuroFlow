import math
from typing import Dict

import numpy as np


def _detrend(signal: np.ndarray) -> np.ndarray:
    return signal - np.mean(signal)


def _band_energy(signal: np.ndarray, fs: float, low: float, high: float) -> float:
    signal = _detrend(signal.astype(np.float64))

    if signal.size < 8:
        return 0.0

    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / fs)

    mask = (freqs >= low) & (freqs <= high)

    if not np.any(mask):
        return 0.0

    return float(np.sum(power[mask]))


def _dominant_frequency(signal: np.ndarray, fs: float, low: float = 0.5, high: float = 15.0) -> float:
    signal = _detrend(signal.astype(np.float64))

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


def _extract_one_signal_features(signal: np.ndarray, fs: float, prefix: str) -> Dict[str, float]:
    signal = signal.astype(np.float64)
    signal_detrended = _detrend(signal)

    q75, q25 = np.percentile(signal, [75, 25])

    total_energy = _band_energy(signal, fs, 0.5, 15.0)
    energy_0_3 = _band_energy(signal, fs, 0.5, 3.0)
    energy_3_8 = _band_energy(signal, fs, 3.0, 8.0)
    energy_4_6 = _band_energy(signal, fs, 4.0, 6.0)
    energy_8_12 = _band_energy(signal, fs, 8.0, 12.0)

    eps = 1e-8

    return {
        f"{prefix}_mean": float(np.mean(signal)),
        f"{prefix}_std": float(np.std(signal)),
        f"{prefix}_rms": float(math.sqrt(np.mean(signal_detrended ** 2))),
        f"{prefix}_min": float(np.min(signal)),
        f"{prefix}_max": float(np.max(signal)),
        f"{prefix}_ptp": float(np.ptp(signal)),
        f"{prefix}_median": float(np.median(signal)),
        f"{prefix}_iqr": float(q75 - q25),
        f"{prefix}_dom_freq": _dominant_frequency(signal, fs),
        f"{prefix}_energy_0p5_3hz": energy_0_3,
        f"{prefix}_energy_3_8hz": energy_3_8,
        f"{prefix}_energy_4_6hz": energy_4_6,
        f"{prefix}_energy_8_12hz": energy_8_12,
        f"{prefix}_ratio_4_6_to_total": float(energy_4_6 / (total_energy + eps)),
        f"{prefix}_ratio_8_12_to_total": float(energy_8_12 / (total_energy + eps)),
        f"{prefix}_ratio_3_8_to_total": float(energy_3_8 / (total_energy + eps)),
    }


def extract_mpu_window_features(
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    gx: np.ndarray,
    gy: np.ndarray,
    gz: np.ndarray,
    sampling_rate_hz: float,
) -> Dict[str, float]:
    """
    Extract fitur dari satu window raw MPU.

    Input harus berupa satu window:
    ax, ay, az, gx, gy, gz

    Output berupa dictionary fitur yang dipakai training dan inference.
    """

    ax = np.asarray(ax, dtype=np.float64)
    ay = np.asarray(ay, dtype=np.float64)
    az = np.asarray(az, dtype=np.float64)
    gx = np.asarray(gx, dtype=np.float64)
    gy = np.asarray(gy, dtype=np.float64)
    gz = np.asarray(gz, dtype=np.float64)

    acc_mag = np.sqrt(ax ** 2 + ay ** 2 + az ** 2)
    gyro_mag = np.sqrt(gx ** 2 + gy ** 2 + gz ** 2)

    signals = {
        "acc_x": ax,
        "acc_y": ay,
        "acc_z": az,
        "gyro_x": gx,
        "gyro_y": gy,
        "gyro_z": gz,
        "acc_mag": acc_mag,
        "gyro_mag": gyro_mag,
    }

    features: Dict[str, float] = {}

    for name, signal in signals.items():
        features.update(
            _extract_one_signal_features(
                signal=signal,
                fs=sampling_rate_hz,
                prefix=name,
            )
        )

    return features
