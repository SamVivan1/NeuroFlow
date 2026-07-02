import { NextRequest, NextResponse } from "next/server";

const ML_SERVICE_URL =
  process.env.ML_SERVICE_URL ?? "http://127.0.0.1:8001";

export async function POST(request: NextRequest) {
  try {
    const payload = await request.json();

    const response = await fetch(`${ML_SERVICE_URL}/predict/features`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        {
          error: "ML service request failed",
          detail: data,
        },
        { status: response.status },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to call ML service",
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}
