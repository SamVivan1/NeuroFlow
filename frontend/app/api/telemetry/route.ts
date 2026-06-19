import {
  ensureConnected,
  subscribeTelemetry,
} from "@/lib/mqtt-bridge";
import type { NeuroflowTelemetry } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  await ensureConnected();

  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;

  const stream = new ReadableStream({
    start(controller) {
      const send = (data: NeuroflowTelemetry) => {
        const payload = JSON.stringify({
          ...data,
          received_at: Date.now(),
        });
        controller.enqueue(encoder.encode(`data: ${payload}\n\n`));
      };

      unsubscribe = subscribeTelemetry(send);

      const keepAlive = setInterval(() => {
        controller.enqueue(encoder.encode(": keepalive\n\n"));
      }, 15000);

      (controller as { _keepAlive?: ReturnType<typeof setInterval> })._keepAlive =
        keepAlive;
    },
    cancel() {
      unsubscribe?.();
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
