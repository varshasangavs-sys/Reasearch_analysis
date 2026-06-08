/**
 * Root layout — the HTML shell shared by every page (we only have one page).
 *
 * Why fonts load here:
 *   next/font self-hosts Google Fonts at BUILD TIME — no FOUT, no third-party
 *   request, no layout shift. The CSS variables it injects (--font-serif,
 *   --font-sans) are then referenced by tailwind.config.ts and globals.css.
 *   One declaration, every component picks them up.
 *
 * Why this is a server component:
 *   It has no interactivity. Server components ship zero JS to the browser
 *   for their own code — only the children that need it.
 */

import type { Metadata } from "next";
import { IBM_Plex_Sans, Newsreader } from "next/font/google";
import "./globals.css";

const serif = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Research Copilot",
  description:
    "A multi-agent research copilot. Decompose, retrieve, critique, synthesize — cited.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
