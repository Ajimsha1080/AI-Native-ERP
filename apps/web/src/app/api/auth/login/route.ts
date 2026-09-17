import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email, password } = body;

    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail || "Authentication failed" },
        { status: res.status }
      );
    }

    const { access_token, refresh_token, expires_in } = data;
    const isProduction = process.env.NODE_ENV === "production";

    const response = NextResponse.json({
      success: true,
      user: { email },
      access_token,
    });

    response.cookies.set("access_token", access_token, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      maxAge: expires_in || 1800,
      path: "/",
    });

    response.cookies.set("refresh_token", refresh_token, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      maxAge: 7 * 24 * 60 * 60,
      path: "/",
    });

    response.cookies.set("user_email", email, {
      httpOnly: false,
      secure: isProduction,
      sameSite: "lax",
      maxAge: 7 * 24 * 60 * 60,
      path: "/",
    });

    return response;
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Internal server error" },
      { status: 500 }
    );
  }
}
