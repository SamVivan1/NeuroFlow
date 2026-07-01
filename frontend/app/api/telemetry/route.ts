import { NextRequest } from "next/server";
import { getLatestTelemetry } from "@/lib/mqtt-bridge";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  let isClosed = false;
  let telemetryInterval: ReturnType<typeof setInterval> | null = null;
  let keepAliveInterval: ReturnType<typeof setInterval> | null = null;

  const fallbackTelemetry = {
  stress_level: 0,
  heart_rate: 0,
  tremor_intensity: 0,
  device_status: "disconnected",
  received_at: Date.now(),

  ax: 0,
  ay: 0,
  az: 0,
  gx: 0,
  gy: 0,
  gz: 0,
};
  const stream = new ReadableStream({
    start(controller) {
      function cleanup() {
        if (isClosed) return;

        isClosed = true;

        if (telemetryInterval) {
          clearInterval(telemetryInterval);
          telemetryInterval = null;
        }

        if (keepAliveInterval) {
          clearInterval(keepAliveInterval);
          keepAliveInterval = null;
        }

        try {
          controller.close();
        } catch {
          // Client may already have closed the stream.
        }
      }

      function safeEnqueue(payload: string) {
        if (isClosed) return;

        try {
          controller.enqueue(encoder.encode(payload));
        } catch {
          cleanup();
        }
      }

      function sendTelemetry() {
        const telemetry = getLatestTelemetry();

        const payload = telemetry ?? {
          ...fallbackTelemetry,
          received_at: Date.now(),
        };

        safeEnqueue(`data: ${JSON.stringify(payload)}\n\n`);
      }

      sendTelemetry();

      telemetryInterval = setInterval(() => {
        sendTelemetry();
      }, 1000);

      keepAliveInterval = setInterval(() => {
        safeEnqueue(": keepalive\n\n");
      }, 15000);

      request.signal.addEventListener("abort", cleanup);
    },

    cancel() {
      isClosed = true;

      if (telemetryInterval) {
        clearInterval(telemetryInterval);
        telemetryInterval = null;
      }

      if (keepAliveInterval) {
        clearInterval(keepAliveInterval);
        keepAliveInterval = null;
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}