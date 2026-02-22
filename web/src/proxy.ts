import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export async function proxy(req: NextRequest) {
  const session = await auth.api.getSession({ headers: req.headers });
  const { pathname } = req.nextUrl;

  // Protect dashboard and setup routes — require session
  if ((pathname.startsWith("/dashboard") || pathname === "/setup") && !session) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  // Redirect already-authenticated users away from login/signup
  if (session && (pathname === "/login" || pathname === "/signup")) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/signup", "/setup"],
};
