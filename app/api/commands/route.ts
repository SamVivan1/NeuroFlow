import { publishCommand } from "@/lib/mqtt-bridge";
import type { DeviceCommands } from "@/lib/types";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as DeviceCommands;
    await publishCommand(body);
    return NextResponse.json({ ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Command failed";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
