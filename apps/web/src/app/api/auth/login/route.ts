import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email, password } = body;

    // 1. Authenticate against real backend
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();

    // 2. Stop-Ship: NEVER fabricate tokens if backend fails. Return actual error.
    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail || "Authentication failed" },
        { status: res.status }
      );
    }

    const { access_token, refresh_token, expires_in } = data;

    // 3. Derive user and role from /auth/me using the validated token
    let userProfile = null;
    try {
      const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${access_token}`,
        },
      });
      if (meRes.ok) {
        userProfile = await meRes.json();
      }
    } catch {
      // Fallback if me endpoint is unreachable
    }

    const isProduction = process.env.NODE_ENV === "production";

    const response = NextResponse.json({
      success: true,
      user: userProfile || { email },
      access_token,
    });

    // 4. Secure HttpOnly cookies for tokens
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

    // 5. Purge unauthenticated/spoofable client cookies (user_role, user_email)
    response.cookies.set("user_email", "", {
      httpOnly: false,
      expires: new Date(0),
      path: "/",
    });

    response.cookies.set("user_role", "", {
      httpOnly: false,
      expires: new Date(0),
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
