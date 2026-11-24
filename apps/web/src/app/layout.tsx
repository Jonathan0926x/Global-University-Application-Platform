import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/navigation/Header";

export const metadata: Metadata = {
  title: "UniGlobe — One Student Profile. Every University. One Global Platform.",
  description:
    "The world's first universal global college application and admissions intelligence platform. Seamless support for both first-year and transfer applicants worldwide.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#fafafc] text-zinc-900 antialiased selection:bg-zinc-900 selection:text-white">
        <Header />
        <main>{children}</main>
      </body>
    </html>
  );
}
