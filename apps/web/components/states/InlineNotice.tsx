import React from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

interface InlineNoticeProps {
  tone: "success" | "error";
  children: React.ReactNode;
  className?: string;
}

/** Small success/error message inside a card or form. Errors are announced to screen readers. */
export function InlineNotice({ tone, children, className = "" }: InlineNoticeProps) {
  const styles =
    tone === "success"
      ? "bg-emerald-50 border-emerald-200 text-emerald-800"
      : "bg-rose-50 border-rose-200 text-rose-800";
  const Icon = tone === "success" ? CheckCircle2 : AlertCircle;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`p-3 border rounded-xl text-xs font-medium flex items-center gap-2 ${styles} ${className}`}
    >
      <Icon className="w-4 h-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
