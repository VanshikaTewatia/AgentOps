"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  ShieldCheck,
  AlertTriangle,
  Server,
  BarChart3,
  Terminal,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Agent Runs", href: "/runs", icon: Bot },
  { name: "Approvals", href: "/approvals", icon: ShieldCheck },
  { name: "Incidents", href: "/incidents", icon: AlertTriangle },
  { name: "Services", href: "/services", icon: Server },
  { name: "Evaluations", href: "/evaluations", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname() || "/";

  return (
    <aside className="w-64 border-r border-gray-800 bg-[#0c121e] flex flex-col shrink-0">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-gray-800 gap-3">
        <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow-md shadow-blue-500/20">
          <Terminal className="h-5 w-5" />
        </div>
        <div>
          <h1 className="font-bold text-base tracking-wide text-white flex items-center gap-1.5">
            AGENT<span className="text-blue-500">OPS</span>
          </h1>
          <p className="text-[10px] text-gray-400 font-mono tracking-tight uppercase">
            Agentic AI Operations
          </p>
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navigation.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50"
              )}
            >
              <Icon className={cn("h-4 w-4", isActive ? "text-blue-400" : "text-gray-500")} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div className="p-4 border-t border-gray-800 text-xs text-gray-400 space-y-2">
        <div className="flex items-center justify-between font-mono">
          <span>LangGraph Core</span>
          <span className="text-emerald-400 font-semibold">ACTIVE</span>
        </div>
        <div className="flex items-center justify-between font-mono">
          <span>Security Policy</span>
          <span className="text-amber-400 font-semibold">ASSISTED</span>
        </div>
      </div>
    </aside>
  );
}
