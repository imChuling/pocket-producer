import type { Metadata, Viewport } from "next";
import { Cormorant, Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";
import { ServiceWorkerRegister } from "@/components/service-worker-register";
import { TopNav } from "@/components/top-nav";

const cormorant = Cormorant({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-cormorant",
});

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-ibm-plex-mono",
});

export const metadata: Metadata = {
  title: "Pocket Producer",
  description: "AI-powered creative memory for music makers",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Pocket Producer",
    statusBarStyle: "default",
  },
};

export const viewport: Viewport = {
  themeColor: "#fdfcfc",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`h-full antialiased ${cormorant.variable} ${inter.variable} ${ibmPlexMono.variable}`}>
      <body className="min-h-full flex flex-col bg-[#fdfcfc]">
        <AuthProvider>
          <ServiceWorkerRegister />
          <TopNav />
          <main className="flex-1 w-full">
            {children}
          </main>
        </AuthProvider>
      </body>
    </html>
  );
}
