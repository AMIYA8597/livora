"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { TokenResponse } from "@flatmate/contracts";
import { Button, Input, Card } from "@flatmate/ui";
import { Home } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"seeker" | "owner">("seeker");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await apiClient<TokenResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          role,
        }),
      });
      login(
        {
          access_token: res.access_token,
          refresh_token: res.refresh_token,
          token_type: res.token_type,
          expires_in: res.expires_in,
        },
        res.user
      );
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Failed to create account. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <Card className="max-w-md w-full p-8 shadow-xl border-slate-200/80">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-indigo-600 rounded-2xl flex items-center justify-center text-white mx-auto mb-3 shadow-md shadow-indigo-200">
            <Home className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Create an Account</h2>
          <p className="text-xs text-slate-500 mt-1">
            Join thousands finding compatible roommates and co-living homes.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Role Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">I want to:</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setRole("seeker")}
                className={`py-2 px-3 text-xs font-semibold rounded-xl border text-center transition-all ${
                  role === "seeker"
                    ? "bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                Find Flatmates / Room
              </button>
              <button
                type="button"
                onClick={() => setRole("owner")}
                className={`py-2 px-3 text-xs font-semibold rounded-xl border text-center transition-all ${
                  role === "owner"
                    ? "bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                List a Room / Property
              </button>
            </div>
          </div>

          <Input
            label="Full Name"
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Alex Morgan"
          />

          <Input
            label="Email Address"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="alex@example.com"
          />

          <Input
            label="Password (min 8 characters)"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isLoading}>
            Create Account
          </Button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-indigo-600 hover:text-indigo-700">
            Sign in
          </Link>
        </div>
      </Card>
    </div>
  );
}
