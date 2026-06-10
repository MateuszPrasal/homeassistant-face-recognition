import type { Metadata } from "next";
import { Fira_Sans, Fira_Code } from "next/font/google";
import "./globals.css";

const firaSans = Fira_Sans({
  variable: "--font-fira-sans",
  weight: ["300", "400", "500", "600", "700"],
  subsets: ["latin", "latin-ext"],
});

const firaCode = Fira_Code({
  variable: "--font-fira-code",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: "Rozpoznawanie twarzy — panel",
  description: "Panel zarządzania rozpoznawaniem twarzy (Home Assistant)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pl"
      className={`${firaSans.variable} ${firaCode.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
