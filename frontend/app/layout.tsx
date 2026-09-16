import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataPilot",
  description: "Agentic EDA & feature engineering assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
