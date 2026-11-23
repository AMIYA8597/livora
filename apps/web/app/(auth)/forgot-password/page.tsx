"use client";

import React, { useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { Button, Input, Card } from "@flatmate/ui";
import { KeyRound, ArrowLeft, CheckCircle2 } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [devResetToken, setDevResetToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setDevResetToken(null);
    setIsLoading(true);

    try {
      const res = await apiClient<{ success: boolean; message: string; reset_token?: string }>(
        "/auth/forgot-password",
        {
          method: "POST",
          body: JSON.stringify({ email }),
        }
      );
      setSuccessMsg(res.message);
      if (res.reset_token) {
        setDevResetToken(res.reset_token);
      }
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to process request. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <Card className="max-w-md w-full p-8 shadow-xl border-slate-200/80">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-indigo-600 rounded-2xl flex items-center justify-center text-white mx-auto mb-3 shadow-md shadow-indigo-200">
            <KeyRound className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Forgot Password?</h2>
          <p className="text-xs text-slate-500 mt-1">
            Enter your registered email address and we&apos;ll issue password recovery instructions.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-xs">
            {error}
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs space-y-2">
            <div className="flex items-center space-x-1.5 font-semibold text-emerald-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Instructions Sent</span>
            </div>
            <p>{successMsg}</p>
            {devResetToken && (
              <div className="pt-2 border-t border-emerald-200 mt-2">
                <span className="font-semibold block text-[11px] text-emerald-900">Direct Reset Link (Local Dev Mode):</span>
                <Link
                  href={`/reset-password?token=${devResetToken}`}
                  className="text-indigo-600 font-bold underline text-xs break-all"
                >
                  Click here to set your new password
                </Link>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Registered Email Address"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isLoading}>
            Send Recovery Link
          </Button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-500">
          <Link href="/login" className="inline-flex items-center min-h-[44px] text-slate-600 hover:text-indigo-600 font-semibold">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            <span>Back to Sign In</span>
          </Link>
        </div>
      </Card>
    </div>
  );
}
