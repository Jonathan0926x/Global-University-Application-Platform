import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/navigation/Header";
import { I18nProvider } from "@/lib/i18n/context";

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
    <html lang="en" dir="ltr">
      <body className="min-h-screen bg-[#fafafc] text-zinc-900 antialiased selection:bg-zinc-900 selection:text-white">
        <I18nProvider>
          <Header />
          <main>{children}</main>
        </I18nProvider>
      </body>
    </html>
  );
}
