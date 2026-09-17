import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const response = NextResponse.json({ success: true, message: "Logged out" });
  
  response.cookies.set("access_token", "", {
    httpOnly: true,
    expires: new Date(0),
    path: "/",
  });

  response.cookies.set("refresh_token", "", {
    httpOnly: true,
    expires: new Date(0),
    path: "/",
  });

  response.cookies.set("user_email", "", {
    httpOnly: false,
    expires: new Date(0),
    path: "/",
  });

  return response;
}
