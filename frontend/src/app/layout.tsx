import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

/** Tell the browser this is a light-only UI, so native chrome matches. */
export const viewport = { colorScheme: "light" as const };

export const metadata: Metadata = {
  title: {
    default: "UBM Growth Engine",
    template: "%s · UBM Growth Engine",
  },
  description:
    "B2B growth opportunity engine for Upshot Brand Media: define targets, discover companies and collect source-backed evidence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
