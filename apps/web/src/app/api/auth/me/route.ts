import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const accessToken = req.cookies.get("access_token")?.value;
  const email = req.cookies.get("user_email")?.value;
  const role = req.cookies.get("user_role")?.value || "admin";

  if (!accessToken) {
    return NextResponse.json(
      { authenticated: false, user: null },
      { status: 401 }
    );
  }

  return NextResponse.json({
    authenticated: true,
    user: {
      email: email || "admin@acmeindustrial.com",
      role: role,
      full_name: (email || "admin@acmeindustrial.com").split("@")[0].toUpperCase(),
    },
    token: accessToken,
  });
}
