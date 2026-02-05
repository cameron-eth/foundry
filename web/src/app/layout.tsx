import type { Metadata } from "next";
import { Outfit, JetBrains_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Foundry - AI Agents Building Tools for Themselves",
  description: "Dynamic tool creation at runtime. Describe what you need, get production-ready code in seconds.",
  openGraph: {
    title: "Foundry - AI Agents Building Tools for Themselves",
    description: "Dynamic tool creation at runtime. Describe what you need, get production-ready code in seconds.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${outfit.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
