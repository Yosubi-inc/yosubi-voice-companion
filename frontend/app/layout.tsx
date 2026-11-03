import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sparks, your community companion" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
