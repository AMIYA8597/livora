"use client";

import React, { useEffect, useState } from "react";
import type { SendEmailCodeResponse, UserTrustStatusDTO } from "@flatmate/contracts";
import { Badge, Button, Input } from "@flatmate/ui";
import { AlertCircle, Briefcase, CheckCircle2, GraduationCap } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { badgeLabel, emailHint, type EmailKind } from "@/lib/verification-model";

interface VerificationFormProps {
  trust: UserTrustStatusDTO | null | undefined;
  /** Called with the refreshed trust status after an email is verified. */
  onVerified?: (status: UserTrustStatusDTO) => void;
}

const KINDS: { value: EmailKind; label: string; icon: typeof Briefcase; placeholder: string }[] = [
  { value: "work_email", label: "Work email", icon: Briefcase, placeholder: "you@company.com" },
  { value: "student_email", label: "College email", icon: GraduationCap, placeholder: "you@college.ac.in" },
];

function formatDate(iso?: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * Verify a work or college email with a one-time code. Only the domain is kept and shown as the
 * badge. ID-document checks are switched off until a KYC provider is chosen.
 */
export function VerificationForm({ trust, onVerified }: VerificationFormProps) {
  const { refreshUser } = useAuth();
  const [kind, setKind] = useState<EmailKind>("work_email");
  const [email, setEmail] = useState("");
  // Domain the latest code went to in this session; a code sent earlier comes from `trust.pending`.
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [ignorePending, setIgnorePending] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<"send" | "verify" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [resendAt, setResendAt] = useState<number | null>(null);
  const [clock, setClock] = useState(() => Date.now());

  useEffect(() => {
    if (resendAt === null) return;
    const id = setInterval(() => {
      const now = Date.now();
      setClock(now);
      if (now >= resendAt) setResendAt(null);
    }, 1000);
    return () => clearInterval(id);
  }, [resendAt]);

  const resendIn = resendAt === null ? 0 : Math.max(0, Math.ceil((resendAt - clock) / 1000));
  const pendingDomain = sentTo ?? (ignorePending ? null : trust?.pending?.email_domain ?? null);
  const verified = trust?.verifications ?? [];
  const current = KINDS.find((k) => k.value === kind) ?? KINDS[0];

  const send = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const hint = emailHint(email, kind);
    if (hint) {
      setError(hint);
      return;
    }
    setError(null);
    setSuccess(null);
    setBusy("send");
    try {
      const res = await apiClient<SendEmailCodeResponse>("/verification/email/send", {
        method: "POST",
        body: JSON.stringify({ verification_type: kind, email: email.trim() }),
      });
      if (res.already_verified) {
        setSuccess("This email is already verified.");
        return;
      }
      const now = Date.now();
      setSentTo(res.email_domain);
      setCode("");
      setDevCode(res.dev_code ?? null);
      setClock(now);
      setResendAt(now + (res.resend_after ?? 60) * 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send the code. Please try again.");
    } finally {
      setBusy(null);
    }
  };

  const confirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code from the email.");
      return;
    }
    setError(null);
    setBusy("verify");
    try {
      const status = await apiClient<UserTrustStatusDTO>("/verification/email/confirm", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setSentTo(null);
      setIgnorePending(true);
      setCode("");
      setDevCode(null);
      setResendAt(null);
      setEmail("");
      setSuccess("Verified. Your badge is now on your profile.");
      onVerified?.(status);
      void refreshUser();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed. Please try again.");
    } finally {
      setBusy(null);
    }
  };

  const startOver = () => {
    setSentTo(null);
    setIgnorePending(true);
    setCode("");
    setDevCode(null);
    setError(null);
  };

  return (
    <div className="space-y-4">
      {verified.length > 0 && (
        <ul className="space-y-2">
          {verified.map((v) => (
            <li
              key={`${v.verification_type}-${v.email_domain}`}
              className="flex items-center justify-between gap-2 p-3 rounded-xl border border-forest/20 bg-forest-pale/40 text-sm"
            >
              <span className="flex items-center gap-2 min-w-0">
                <CheckCircle2 className="w-4 h-4 text-forest shrink-0" aria-hidden="true" />
                <span className="font-semibold text-charcoal">{badgeLabel(v.verification_type)}</span>
                <span className="text-charcoal-muted truncate">{v.email_domain}</span>
              </span>
              <span className="text-[11px] text-charcoal-muted shrink-0">{formatDate(v.verified_at)}</span>
            </li>
          ))}
        </ul>
      )}

      {success && (
        <p role="status" className="text-xs text-forest flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          {success}
        </p>
      )}

      {pendingDomain ? (
        <form onSubmit={confirm} className="space-y-2">
          <label htmlFor="verify-code" className="text-xs text-charcoal block">
            Enter the 6-digit code we emailed to your address at <strong>{pendingDomain}</strong>.
          </label>
          <div className="flex flex-col sm:flex-row gap-2">
            <Input
              id="verify-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              className="flex-1 tracking-[0.3em]"
            />
            <Button
              type="submit"
              variant="primary"
              isLoading={busy === "verify"}
              disabled={code.length !== 6 || busy !== null}
              className="min-h-[44px]"
            >
              Verify
            </Button>
          </div>
          {devCode && (
            <span className="text-[10px] text-amber-700 block">Development server: your code is {devCode}</span>
          )}
          <div className="flex flex-wrap gap-3 text-[11px]">
            {sentTo && email && (
              <button
                type="button"
                onClick={() => send()}
                disabled={resendIn > 0 || busy !== null}
                className="min-h-[44px] font-semibold text-forest underline disabled:text-charcoal-muted disabled:no-underline"
              >
                {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
              </button>
            )}
            <button type="button" onClick={startOver} className="min-h-[44px] font-semibold text-forest underline">
              Use a different email
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={send} className="space-y-3">
          <fieldset>
            <legend className="block text-xs font-semibold text-charcoal mb-1.5">What would you like to verify?</legend>
            <div className="grid grid-cols-2 gap-2">
              {KINDS.map((k) => {
                const Icon = k.icon;
                const active = k.value === kind;
                return (
                  <button
                    key={k.value}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setKind(k.value);
                      setError(null);
                    }}
                    className={`min-h-[44px] flex items-center justify-center gap-2 rounded-xl border text-sm font-semibold transition-colors ${
                      active ? "border-forest bg-forest-pale text-forest" : "border-slate-200 bg-white text-charcoal hover:border-forest/40"
                    }`}
                  >
                    <Icon className="w-4 h-4" aria-hidden="true" />
                    {k.label}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <div>
            <label htmlFor="verify-email" className="block text-xs font-semibold text-charcoal mb-1">
              {current.label} address
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <Input
                id="verify-email"
                type="email"
                inputMode="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError(null);
                }}
                placeholder={current.placeholder}
                className="flex-1"
              />
              <Button
                type="submit"
                variant="primary"
                isLoading={busy === "send"}
                disabled={!email.trim() || busy !== null}
                className="min-h-[44px] whitespace-nowrap"
              >
                Send code
              </Button>
            </div>
          </div>
        </form>
      )}

      {error && (
        <p role="alert" className="text-xs text-red-600 flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          {error}
        </p>
      )}

      <div className="text-[11px] text-charcoal-muted space-y-1">
        <p>
          We email a one-time code to prove you use that address. We keep only its domain (like infosys.com), never
          the address. Others see a &quot;verified&quot; badge, not the domain. Personal mailboxes like Gmail
          can&apos;t be verified.
        </p>
        <p>ID document checks aren&apos;t available yet.</p>
      </div>
    </div>
  );
}
