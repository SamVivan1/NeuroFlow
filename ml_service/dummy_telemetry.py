import json
import math
import random
import time
from dataclasses import dataclass

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion


MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "neuroflow/device/data"

FS = 50  # 50 Hz raw MPU
PUBLISH_HZ = 5  # kirim 5 payload/detik
SAMPLES_PER_PAYLOAD = FS // PUBLISH_HZ  # 10 sample/payload


@dataclass
class Scenario:
    name: str
    activity: str
    duration_sec: int

    target_hr: float
    target_stress: float
    target_rmssd: float
    target_sdnn: float
    target_pnn50: float

    tremor_freq_hz: float
    tremor_amp_g: float

    physiologic_freq_hz: float
    physiologic_amp_g: float

    walking_amp_g: float


SCENARIOS = [
    Scenario(
        name="REST_CALM",
        activity="STATIONARY",
        duration_sec=25,
        target_hr=68,
        target_stress=18,
        target_rmssd=58,
        target_sdnn=72,
        target_pnn50=28,
        tremor_freq_hz=4.8,
        tremor_amp_g=0.015,
        physiologic_freq_hz=9.0,
        physiologic_amp_g=0.005,
        walking_amp_g=0.0,
    ),
    Scenario(
        name="BASELINE_PARKINSON_TREMOR",
        activity="STATIONARY",
        duration_sec=35,
        target_hr=73,
        target_stress=34,
        target_rmssd=43,
        target_sdnn=56,
        target_pnn50=17,
        tremor_freq_hz=4.9,
        tremor_amp_g=0.080,
        physiologic_freq_hz=9.0,
        physiologic_amp_g=0.008,
        walking_amp_g=0.0,
    ),
    Scenario(
        name="STRESS_AMPLIFIED_TREMOR",
        activity="STATIONARY",
        duration_sec=40,
        target_hr=96,
        target_stress=82,
        target_rmssd=18,
        target_sdnn=30,
        target_pnn50=4,
        tremor_freq_hz=5.1,
        tremor_amp_g=0.220,
        physiologic_freq_hz=9.5,
        physiologic_amp_g=0.030,
        walking_amp_g=0.0,
    ),
    Scenario(
        name="RECOVERY",
        activity="STATIONARY",
        duration_sec=30,
        target_hr=79,
        target_stress=45,
        target_rmssd=35,
        target_sdnn=48,
        target_pnn50=12,
        tremor_freq_hz=5.0,
        tremor_amp_g=0.105,
        physiologic_freq_hz=9.0,
        physiologic_amp_g=0.015,
        walking_amp_g=0.0,
    ),
    Scenario(
        name="WALKING_ARTIFACT",
        activity="WALKING",
        duration_sec=25,
        target_hr=86,
        target_stress=38,
        target_rmssd=38,
        target_sdnn=52,
        target_pnn50=13,
        tremor_freq_hz=4.8,
        tremor_amp_g=0.030,
        physiologic_freq_hz=9.0,
        physiologic_amp_g=0.008,
        walking_amp_g=0.240,
    ),
    Scenario(
        name="TYPING_ARTIFACT",
        activity="TYPING",
        duration_sec=20,
        target_hr=82,
        target_stress=40,
        target_rmssd=40,
        target_sdnn=55,
        target_pnn50=15,
        tremor_freq_hz=0.0,
        tremor_amp_g=0.0,
        physiologic_freq_hz=0.0,
        physiologic_amp_g=0.0,
        walking_amp_g=0.0,
    ),
    Scenario(
        name="ANXIOUS_HIGH_FREQ_PHYSIOLOGIC_TREMOR",
        activity="STATIONARY",
        duration_sec=30,
        target_hr=90,
        target_stress=70,
        target_rmssd=24,
        target_sdnn=36,
        target_pnn50=7,
        tremor_freq_hz=0.0,
        tremor_amp_g=0.0,
        physiologic_freq_hz=9.5,
        physiologic_amp_g=0.075,
        walking_amp_g=0.0,
    ),
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smooth(current: float, target: float, alpha: float) -> float:
    return current + ((target - current) * alpha)


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[Dummy Telemetry] Connected to MQTT broker: {reason_code}")


def build_sample(
    sample_index: int,
    scenario: Scenario,
    tremor_amp: float,
    tremor_freq: float,
    physiologic_amp: float,
    physiologic_freq: float,
    walking_amp: float,
    start_epoch_ms: int,
):
    t = sample_index / FS

    timestamp_ms = start_epoch_ms + int(t * 1000)

    # Drift halus seperti perubahan posisi tangan.
    posture_drift = 0.035 * math.sin(2 * math.pi * 0.07 * t)
    breathing_motion = 0.010 * math.sin(2 * math.pi * 0.25 * t)

    # Tremor Parkinson-band sekitar 4-6 Hz.
    tremor = tremor_amp * math.sin(2 * math.pi * tremor_freq * t)

    # High-frequency physiologic-like tremor sekitar 8-12 Hz.
    physiologic = physiologic_amp * math.sin(2 * math.pi * physiologic_freq * t + 0.8)

    # Walking artifact sekitar 1-2 Hz.
    walking_vertical = walking_amp * math.sin(2 * math.pi * 1.85 * t)
    walking_lateral = 0.55 * walking_amp * math.sin(2 * math.pi * 1.85 * t + 1.2)
    
    typing_spike = 0.0
    if scenario.activity == "TYPING" and random.random() < 0.15:
        typing_spike = random.gauss(0, 0.45) # High acceleration spike -> high jerk

    noise_acc = lambda: random.gauss(0, 0.008)
    noise_gyro = lambda: random.gauss(0, 0.040)

    # Orientasi gravitasi dasar: az sekitar 1g.
    ax = (
        0.020 * math.sin(2 * math.pi * 0.11 * t)
        + 0.35 * tremor
        + 0.30 * physiologic
        + walking_lateral
        + typing_spike
        + noise_acc()
    )

    ay = (
        -0.015 * math.sin(2 * math.pi * 0.09 * t + 0.4)
        + 0.25 * tremor
        + 0.20 * physiologic
        + 0.35 * walking_lateral
        + noise_acc()
    )

    az = (
        1.0
        + posture_drift
        + breathing_motion
        + 0.65 * tremor
        + 0.25 * physiologic
        + walking_vertical
        + noise_acc()
    )

    gx = (
        1.8 * tremor
        + 0.9 * physiologic
        + 1.2 * walking_lateral
        + noise_gyro()
    )

    gy = (
        1.4 * tremor
        + 0.6 * physiologic
        + 0.8 * walking_vertical
        + noise_gyro()
    )

    gz = (
        0.8 * tremor
        + 0.5 * physiologic
        + 0.5 * walking_lateral
        + noise_gyro()
    )

    return {
        "timestamp": timestamp_ms,
        "ax": round(ax, 6),
        "ay": round(ay, 6),
        "az": round(az, 6),
        "gx": round(gx, 6),
        "gy": round(gy, 6),
        "gz": round(gz, 6),
    }


def main():
    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    print("[Dummy Telemetry] Starting human-like telemetry stream...")
    print("[Dummy Telemetry] Press Ctrl+C to stop.")

    scenario_index = 0
    scenario = SCENARIOS[scenario_index]
    scenario_started = time.monotonic()

    hr = scenario.target_hr
    stress = scenario.target_stress
    rmssd = scenario.target_rmssd
    sdnn = scenario.target_sdnn
    pnn50 = scenario.target_pnn50

    tremor_amp = scenario.tremor_amp_g
    tremor_freq = scenario.tremor_freq_hz
    physiologic_amp = scenario.physiologic_amp_g
    physiologic_freq = scenario.physiologic_freq_hz
    walking_amp = scenario.walking_amp_g

    battery_pct = 92.0
    spo2 = 98.0

    start_epoch_ms = int(time.time() * 1000)
    sample_index = 0

    next_publish_time = time.monotonic()

    print(f"[Condition] {scenario.name}")

    try:
        while True:
            now = time.monotonic()

            if now - scenario_started >= scenario.duration_sec:
                scenario_index = (scenario_index + 1) % len(SCENARIOS)
                scenario = SCENARIOS[scenario_index]
                scenario_started = now
                print(f"[Condition] {scenario.name}")

            # Smooth transition supaya tidak loncat-loncat.
            hr = smooth(hr, scenario.target_hr, 0.035) + random.gauss(0, 0.08)
            stress = smooth(stress, scenario.target_stress, 0.035) + random.gauss(0, 0.12)
            rmssd = smooth(rmssd, scenario.target_rmssd, 0.040) + random.gauss(0, 0.10)
            sdnn = smooth(sdnn, scenario.target_sdnn, 0.040) + random.gauss(0, 0.12)
            pnn50 = smooth(pnn50, scenario.target_pnn50, 0.045) + random.gauss(0, 0.05)

            tremor_amp = smooth(tremor_amp, scenario.tremor_amp_g, 0.045)
            tremor_freq = smooth(tremor_freq, scenario.tremor_freq_hz, 0.020)
            physiologic_amp = smooth(physiologic_amp, scenario.physiologic_amp_g, 0.045)
            physiologic_freq = smooth(physiologic_freq, scenario.physiologic_freq_hz, 0.020)
            walking_amp = smooth(walking_amp, scenario.walking_amp_g, 0.050)

            hr = clamp(hr, 50, 125)
            stress = clamp(stress, 0, 100)
            rmssd = clamp(rmssd, 8, 90)
            sdnn = clamp(sdnn, 15, 100)
            pnn50 = clamp(pnn50, 0, 45)

            # Battery turun perlahan.
            battery_pct = clamp(battery_pct - 0.0008, 5, 100)

            # SpO2 stabil dengan noise kecil.
            spo2 = clamp(smooth(spo2, 98.0, 0.020) + random.gauss(0, 0.02), 94, 100)

            samples = []

            for _ in range(SAMPLES_PER_PAYLOAD):
                sample = build_sample(
                    sample_index=sample_index,
                    scenario=scenario,
                    tremor_amp=tremor_amp,
                    tremor_freq=tremor_freq,
                    physiologic_amp=physiologic_amp,
                    physiologic_freq=physiologic_freq,
                    walking_amp=walking_amp,
                    start_epoch_ms=start_epoch_ms,
                )
                samples.append(sample)
                sample_index += 1

            last_sample = samples[-1]

            tremor_score = clamp(
                (tremor_amp / 0.25) * 75
                + (physiologic_amp / 0.08) * 18
                + (walking_amp / 0.25) * 12,
                0,
                100,
            )

            payload = {
                "schema_version": "neuroflow.dummy.v2",
                "condition": scenario.name,
                "activity": scenario.activity,

                "heart_rate": int(round(hr)),
                "avg_bpm_30s": int(round(hr + random.gauss(0, 1.2))),
                "stress_level": int(round(stress)),
                "tremor_intensity": int(round(tremor_score)),

                "rmssd": round(rmssd, 2),
                "sdnn": round(sdnn, 2),
                "pnn50": round(pnn50, 2),
                "spo2": int(round(spo2)),
                "battery_pct": int(round(battery_pct)),

                "device_status": "connected",
                "received_at": int(time.time() * 1000),
                "sampling_rate_hz": FS,
                "window_size": len(samples),

                # Top-level raw MPU supaya frontend parser sekarang tetap bisa baca.
                "ax": last_sample["ax"],
                "ay": last_sample["ay"],
                "az": last_sample["az"],
                "gx": last_sample["gx"],
                "gy": last_sample["gy"],
                "gz": last_sample["gz"],

                # Full raw window untuk backend/model yang membaca window.
                "samples": samples,
            }

            client.publish(MQTT_TOPIC, json.dumps(payload), qos=0)

            print(
                f"[{scenario.name}] "
                f"HR={payload['heart_rate']} "
                f"Stress={payload['stress_level']} "
                f"RMSSD={payload['rmssd']} "
                f"Tremor={payload['tremor_intensity']} "
                f"MPU=({payload['ax']}, {payload['ay']}, {payload['az']})"
            )

            next_publish_time += 1.0 / PUBLISH_HZ
            sleep_time = next_publish_time - time.monotonic()

            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Kalau komputer sempat lag, jangan akumulasi delay terlalu parah.
                next_publish_time = time.monotonic()

    except KeyboardInterrupt:
        print("\n[Dummy Telemetry] Stopping...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()