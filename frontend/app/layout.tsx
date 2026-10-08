import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { Sidebar } from "@/components/common/Sidebar";
import { Header } from "@/components/common/Header";
import { LoadingSpinner } from "@/components/common/StateComponents";

export const metadata: Metadata = {
  title: "AgentOps — Enterprise Multi-Agent Operations Console",
  description:
    "Autonomous agent orchestration, diagnostic telemetry, runbook RAG, and human approval control center.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#090d16] text-gray-100 flex h-screen overflow-hidden antialiased">
        <Suspense fallback={<div className="w-64 bg-[#0c121e]" />}>
          <Sidebar />
        </Suspense>
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto p-6 bg-[#090d16]">
            <Suspense fallback={<LoadingSpinner label="Loading page..." />}>
              {children}
            </Suspense>
          </main>
        </div>
      </body>
    </html>
  );
}
