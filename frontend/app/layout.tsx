import type { Metadata } from "next";
import { Source_Serif_4, Inter } from "next/font/google";
import { OriginalHeadlineProvider } from "@/lib/OriginalHeadlineContext";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "The Bright Side",
  description: "Real news, honestly framed — what's true, what's serious, and what's genuinely being done about it.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${sourceSerif.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">
        <OriginalHeadlineProvider>{children}</OriginalHeadlineProvider>
      </body>
    </html>
  );
}
