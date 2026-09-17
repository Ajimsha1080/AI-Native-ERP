import type { Metadata } from "next";
import "./globals.css";
import AppShell from "../components/AppShell";

export const metadata: Metadata = {
  title: "Agentic ERP Platform",
  description: "Enterprise-grade AI-Native Business Operating Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
