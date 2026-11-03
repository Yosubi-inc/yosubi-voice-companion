import type { Metadata, Viewport } from "next";

export const viewport: Viewport = { themeColor: "#005a9c", width: "device-width", initialScale: 1 };

export const metadata: Metadata = {
  title: "Sparks, your community companion",
  description: "A simple voice assistant for older adults, in English and Spanish.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Sparks", statusBarStyle: "default" },
  icons: { apple: "/apple-touch-icon.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
