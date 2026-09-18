"use client";

import { usePathname } from "next/navigation";
import { AuthProvider } from "../lib/auth-context";
import Sidebar from "./Sidebar";
import CommandPalette from "./CommandPalette";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalonePage =
    pathname === "/login" ||
    pathname === "/signup" ||
    pathname === "/terms" ||
    pathname === "/privacy";

  return (
    <AuthProvider>
      {isStandalonePage ? (
        <main>{children}</main>
      ) : (
        <div className="shell">
          <Sidebar />
          {children}
          <CommandPalette />
        </div>
      )}
    </AuthProvider>
  );
}
