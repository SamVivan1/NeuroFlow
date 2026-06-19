import mqtt, { type MqttClient } from "mqtt";
import type { DeviceCommands, NeuroflowTelemetry } from "./types";
import { parseTelemetryPayload } from "./telemetry-utils";

const BROKER = process.env.MQTT_BROKER ?? "broker.hivemq.com";
const PORT = process.env.MQTT_PORT ?? "1883";
const DATA_TOPIC = process.env.MQTT_TOPIC_DATA ?? "neuroflow/device/data";
const COMMANDS_TOPIC = process.env.MQTT_TOPIC_COMMANDS ?? "neuroflow/device/commands";

type TelemetryListener = (data: NeuroflowTelemetry) => void;

let client: MqttClient | null = null;
let connecting: Promise<MqttClient> | null = null;
let latestTelemetry: NeuroflowTelemetry | null = null;
const listeners = new Set<TelemetryListener>();

function brokerUrl(): string {
  return `mqtt://${BROKER}:${PORT}`;
}

export function getLatestTelemetry(): NeuroflowTelemetry | null {
  return latestTelemetry;
}

export function subscribeTelemetry(listener: TelemetryListener): () => void {
  listeners.add(listener);
  if (latestTelemetry) listener(latestTelemetry);
  void ensureConnected();
  return () => listeners.delete(listener);
}

function notifyListeners(data: NeuroflowTelemetry): void {
  latestTelemetry = data;
  for (const listener of listeners) listener(data);
}

export async function ensureConnected(): Promise<MqttClient> {
  if (client?.connected) return client;
  if (connecting) return connecting;

  connecting = new Promise((resolve, reject) => {
    const mqttClient = mqtt.connect(brokerUrl(), {
      clientId: `neuroflow_web_${Math.random().toString(16).slice(2, 10)}`,
      reconnectPeriod: 5000,
      connectTimeout: 10000,
    });

    mqttClient.on("connect", () => {
      mqttClient.subscribe(DATA_TOPIC, (err) => {
        if (err) {
          reject(err);
          return;
        }
        client = mqttClient;
        connecting = null;
        resolve(mqttClient);
      });
    });

    mqttClient.on("message", (_topic, payload) => {
      const parsed = parseTelemetryPayload(payload.toString());
      if (parsed) notifyListeners(parsed);
    });

    mqttClient.on("error", (err) => {
      console.error("[MQTT Bridge]", err.message);
    });
  });

  return connecting;
}

export async function publishCommand(commands: DeviceCommands): Promise<void> {
  const mqttClient = await ensureConnected();
  return new Promise((resolve, reject) => {
    mqttClient.publish(COMMANDS_TOPIC, JSON.stringify(commands), (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}
