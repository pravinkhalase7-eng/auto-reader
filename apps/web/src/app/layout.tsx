import type { Metadata, Viewport } from "next";
import { Fraunces, Nunito } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
});

const sans = Nunito({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "AI Teacher — Learn from every page",
  description:
    "Upload a textbook page. Read it, listen to it, understand it, and test yourself with your AI Teacher.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${sans.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
