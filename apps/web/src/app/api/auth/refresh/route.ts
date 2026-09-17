import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const refreshToken = req.cookies.get("refresh_token")?.value;

    if (!refreshToken) {
      return NextResponse.json(
        { error: "No refresh token provided" },
        { status: 401 }
      );
    }

    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const data = await res.json();

    if (!res.ok) {
      const response = NextResponse.json(
        { error: "Refresh failed" },
        { status: 401 }
      );
      response.cookies.set("access_token", "", { expires: new Date(0), path: "/" });
      response.cookies.set("refresh_token", "", { expires: new Date(0), path: "/" });
      return response;
    }

    const { access_token, refresh_token: new_refresh_token, expires_in } = data;
    const isProduction = process.env.NODE_ENV === "production";

    const response = NextResponse.json({
      success: true,
      access_token,
    });

    response.cookies.set("access_token", access_token, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      maxAge: expires_in || 1800,
      path: "/",
    });

    if (new_refresh_token) {
      response.cookies.set("refresh_token", new_refresh_token, {
        httpOnly: true,
        secure: isProduction,
        sameSite: "lax",
        maxAge: 7 * 24 * 60 * 60,
        path: "/",
      });
    }

    return response;
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Refresh error" },
      { status: 500 }
    );
  }
}
