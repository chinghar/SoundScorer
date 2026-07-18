import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Singing Similarity Scorer",
  description: "Sing along to a song and see how closely you matched pitch, tone, and lyrics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-gradient-to-br from-blue-600 via-indigo-600 to-red-600 bg-fixed font-sf">
        {children}
      </body>
    </html>
  );
}
