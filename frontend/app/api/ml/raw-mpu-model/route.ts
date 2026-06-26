import { NextRequest, NextResponse } from "next/server";

const ML_SERVICE_URL =
  process.env.ML_SERVICE_URL ?? "http://127.0.0.1:8001";

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();

    const response = await fetch(`${ML_SERVICE_URL}/predict/raw-mpu-model`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });

    const text = await response.text();

    let data: unknown;

    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json(
        {
          error: "ML service returned non-JSON response",
          detail: text.slice(0, 500),
        },
        { status: 502 },
      );
    }

    if (!response.ok) {
      return NextResponse.json(
        {
          error: "Raw MPU model request failed",
          detail: data,
        },
        { status: response.status },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to call raw MPU model service",
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}
