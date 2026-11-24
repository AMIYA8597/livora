"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { safeNextPath } from "@/lib/navigation";
import { TokenResponse } from "@flatmate/contracts";
import { Button, Input, Card } from "@flatmate/ui";
import { Home, Lock, Mail } from "lucide-react";
import { InlineNotice } from "@/components/states/InlineNotice";
import { deletedNoticeDate } from "@/lib/account-data-model";

const DEMO_LOGIN_ENABLED = process.env.NEXT_PUBLIC_DEMO_LOGIN === "true";

/** After someone deletes their account they land here; tell them how to change their mind. */
function DeletionScheduledNotice() {
  const date = deletedNoticeDate(useSearchParams().get("deleted"));
  if (!date) return null;
  return (
    <div className="mb-4">
      <InlineNotice tone="success">
        Your account will be deleted on {date}. Until then it&apos;s hidden; sign in before that date to keep it.
      </InlineNotice>
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [restoredNext, setRestoredNext] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await apiClient<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      login(
        {
          access_token: res.access_token,
          refresh_token: res.refresh_token,
          token_type: res.token_type,
          expires_in: res.expires_in,
        },
        res.user,
        res.roles
      );
      // Back to the page that sent the user here, if it is a safe same-site path.
      const next = safeNextPath(new URLSearchParams(window.location.search).get("next"));
      if (res.account_restored) {
        setRestoredNext(next); // say so before moving on
        return;
      }
      router.replace(next);
    } catch (err: any) {
      setError(err.message || "Failed to log in. Please check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <Card className="max-w-md w-full p-8 shadow-xl border-slate-200/80">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-indigo-600 rounded-2xl flex items-center justify-center text-white mx-auto mb-3 shadow-md shadow-indigo-200">
            <Home className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Welcome Back</h2>
          <p className="text-xs text-slate-500 mt-1">
            Log in to manage your flatmate matches, messages, and applications.
          </p>
        </div>

        {!restoredNext && (
          <Suspense fallback={null}>
            <DeletionScheduledNotice />
          </Suspense>
        )}

        {restoredNext && (
          <div className="mb-4 space-y-3">
            <InlineNotice tone="success">
              Welcome back. Your account deletion was cancelled and your profile and listings are visible again.
            </InlineNotice>
            <Button className="w-full min-h-[44px]" onClick={() => router.replace(restoredNext)}>
              Continue
            </Button>
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email Address"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />

          <Input
            label="Password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />

          <div className="flex justify-end">
            <Link href="/forgot-password" className="inline-flex items-center min-h-[44px] text-xs text-indigo-600 hover:text-indigo-700 font-medium">
              Forgot password?
            </Link>
          </div>

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isLoading}>
            Sign In
          </Button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-500">
          Don&apos;t have an account yet?{" "}
          <Link href="/register" className="font-semibold text-indigo-600 hover:text-indigo-700">
            Create an account
          </Link>
        </div>

        {/* Seeded demo accounts: local development only. Off unless explicitly enabled, so the
            credentials are compiled out of staging and production bundles. */}
        {DEMO_LOGIN_ENABLED && (
        <div className="mt-6 pt-4 border-t border-slate-100 text-center">
          <span className="text-[11px] text-slate-400 block mb-1">Quick Demo Login:</span>
          <div className="flex justify-center gap-2">
            <button
              type="button"
              onClick={() => {
                setEmail("priya@example.com");
                setPassword("Password123!");
              }}
              className="text-xs text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md hover:bg-indigo-100 transition-colors"
            >
              Seeker (Priya)
            </button>
            <button
              type="button"
              onClick={() => {
                setEmail("sarah.owner@example.com");
                setPassword("Password123!");
              }}
              className="text-xs text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md hover:bg-indigo-100 transition-colors"
            >
              Landlord (Sarah)
            </button>
          </div>
        </div>
        )}
      </Card>
    </div>
  );
}
