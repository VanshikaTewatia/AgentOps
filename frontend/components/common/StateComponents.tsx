import React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Clock, Info, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  className?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, className, size = "sm" }: StatusBadgeProps) {
  const norm = status?.toUpperCase() || "UNKNOWN";

  let colorClasses = "bg-gray-800 text-gray-300 border-gray-700";
  let icon = <Info className="h-3 w-3" />;

  if (["COMPLETED", "APPROVED", "HEALTHY", "PASSED", "RESOLVED", "SUCCESS"].includes(norm)) {
    colorClasses = "bg-emerald-950/60 text-emerald-400 border-emerald-800/60";
    icon = <CheckCircle2 className="h-3 w-3" />;
  } else if (["RUNNING", "INVESTIGATING"].includes(norm)) {
    colorClasses = "bg-blue-950/60 text-blue-400 border-blue-800/60 animate-pulse";
    icon = <Clock className="h-3 w-3" />;
  } else if (["WAITING_APPROVAL", "PENDING", "PENDING_APPROVAL", "DEGRADED", "MEDIUM"].includes(norm)) {
    colorClasses = "bg-amber-950/60 text-amber-400 border-amber-800/60";
    icon = <AlertTriangle className="h-3 w-3" />;
  } else if (["FAILED", "REJECTED", "DOWN", "HIGH", "CRITICAL"].includes(norm)) {
    colorClasses = "bg-rose-950/60 text-rose-400 border-rose-800/60";
    icon = <ShieldAlert className="h-3 w-3" />;
  }

  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-semibold";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-mono font-medium tracking-tight",
        sizeClasses,
        colorClasses,
        className
      )}
    >
      {icon}
      {norm}
    </span>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-rose-800/50 bg-rose-950/20 p-6 text-center text-rose-300">
      <AlertCircle className="mx-auto h-8 w-8 text-rose-400 mb-2" />
      <h3 className="font-semibold text-rose-200 text-sm">System Error</h3>
      <p className="mt-1 text-xs text-rose-400 max-w-md mx-auto">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-3 py-1.5 bg-rose-900/60 hover:bg-rose-900 border border-rose-700 text-rose-100 rounded-md text-xs font-medium transition-colors"
        >
          Retry Request
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-[#0e1422] p-8 text-center text-gray-400">
      <Info className="mx-auto h-8 w-8 text-gray-500 mb-2" />
      <h3 className="font-medium text-gray-200 text-sm">{title}</h3>
      <p className="mt-1 text-xs text-gray-400 max-w-sm mx-auto">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md text-xs font-medium transition-colors shadow-sm shadow-blue-500/20"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function LoadingSpinner({ label = "Loading data..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-gray-400">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent mb-3" />
      <span className="text-xs font-mono">{label}</span>
    </div>
  );
}
