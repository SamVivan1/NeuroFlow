import { NextResponse } from "next/server";

const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  try {
    const payload = await request.json();

    const response = await fetch(`${ML_SERVICE_URL}/predict/tremor-stress-context`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const text = await response.text();

    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json(
        { error: "ML service returned non-JSON response", detail: text.slice(0, 500) },
        { status: 502 },
      );
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: "Tremor stress context request failed", detail: data },
        { status: response.status },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to call ML service", detail: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
