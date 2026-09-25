import type { Metadata } from "next";
import { Archivo, Inter } from "next/font/google";
import { OriginalHeadlineProvider } from "@/lib/OriginalHeadlineContext";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const archivo = Archivo({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["700", "800", "900"],
});

export const metadata: Metadata = {
  title: "Just News",
  description: "Real news, honestly framed — what's true, what's serious, and what's genuinely being done about it.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${archivo.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">
        <OriginalHeadlineProvider>{children}</OriginalHeadlineProvider>
      </body>
    </html>
  );
}
