import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const accessToken = req.cookies.get("access_token")?.value;
  const email = req.cookies.get("user_email")?.value;

  if (!accessToken) {
    return NextResponse.json(
      { authenticated: false, user: null },
      { status: 401 }
    );
  }

  return NextResponse.json({
    authenticated: true,
    user: {
      email: email || "user@agenticerp.internal",
    },
    token: accessToken,
  });
}
