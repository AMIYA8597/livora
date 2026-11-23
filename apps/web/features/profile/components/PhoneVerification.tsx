"use client";

import React, { useEffect, useState } from "react";
import type { SendOtpResponse, UserDTO, VerifyOtpResponse } from "@flatmate/contracts";
import { Badge, Button, Input } from "@flatmate/ui";
import { AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface PhoneVerificationProps {
  user: UserDTO | null;
  /** Re-read the user after a successful verification. */
  onVerified: () => Promise<void> | void;
  onNotice?: (message: string) => void;
}

const lastTen = (value: string | null | undefined) => (value || "").replace(/\D/g, "").slice(-10);

/** Send an SMS code and confirm it; the number is saved on the account only once verified. */
export function PhoneVerification({ user, onVerified, onNotice }: PhoneVerificationProps) {
  // null = untouched, so the field follows the saved number once the user has loaded.
  const [phoneDraft, setPhoneDraft] = useState<string | null>(null);
  const phoneNumber = phoneDraft ?? user?.phone_number ?? "";
  const [otpSentTo, setOtpSentTo] = useState<string | null>(null);
  const [otpCode, setOtpCode] = useState("");
  const [busy, setBusy] = useState<"send" | "verify" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [resendAt, setResendAt] = useState<number | null>(null);
  const [clock, setClock] = useState(() => Date.now());

  // Ticks only while a resend cooldown is running.
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
  const isVerified = !!user?.phone_verified && !!user.phone_number && lastTen(phoneNumber) === lastTen(user.phone_number);

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const phone = phoneNumber.trim();
    if (!phone) return;
    setError(null);
    setBusy("send");
    try {
      const res = await apiClient<SendOtpResponse>("/auth/otp/send", {
        method: "POST",
        body: JSON.stringify({ phone_number: phone }),
      });
      if (res.already_verified) {
        setOtpSentTo(null);
        onNotice?.("This number is already verified.");
        return;
      }
      const now = Date.now();
      setOtpSentTo(phone);
      setOtpCode("");
      setDevCode(res.dev_code ?? null);
      setClock(now);
      setResendAt(now + (res.resend_after ?? 60) * 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the code. Please try again.");
    } finally {
      setBusy(null);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpSentTo || !/^\d{6}$/.test(otpCode)) {
      setError("Enter the 6-digit code from the SMS.");
      return;
    }
    setError(null);
    setBusy("verify");
    try {
      await apiClient<VerifyOtpResponse>("/auth/otp/verify", {
        method: "POST",
        body: JSON.stringify({ phone_number: otpSentTo, otp_code: otpCode }),
      });
      setOtpSentTo(null);
      setOtpCode("");
      setDevCode(null);
      setResendAt(null);
      setPhoneDraft(null);
      await onVerified();
      onNotice?.("Mobile number verified.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed. Please try again.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-3 bg-warm rounded-xl border border-slate-200/60 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor="phone-number" className="font-semibold text-charcoal block">Mobile phone number</label>
        {isVerified ? (
          <Badge variant="forest">Verified</Badge>
        ) : user?.phone_number && phoneDraft === null ? (
          <Badge variant="warning">Not verified</Badge>
        ) : null}
      </div>
      <form onSubmit={handleSend} className="flex flex-col sm:flex-row gap-2">
        <Input
          id="phone-number"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          value={phoneNumber}
          onChange={(e) => {
            setPhoneDraft(e.target.value);
            setOtpSentTo(null);
            setError(null);
          }}
          placeholder="+91 98765 43210"
          className="flex-1"
        />
        {!isVerified && (
          <Button
            type="submit"
            size="sm"
            variant="primary"
            isLoading={busy === "send"}
            disabled={!phoneNumber.trim() || busy !== null || (!!otpSentTo && resendIn > 0)}
            className="min-h-[44px]"
          >
            {otpSentTo ? (resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code") : "Send code"}
          </Button>
        )}
      </form>

      {otpSentTo && (
        <form onSubmit={handleVerify} className="space-y-2">
          <label htmlFor="phone-otp" className="text-[11px] text-charcoal-muted block">
            Enter the 6-digit code sent to {otpSentTo}
          </label>
          <div className="flex flex-col sm:flex-row gap-2">
            <Input
              id="phone-otp"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="123456"
              className="flex-1 tracking-[0.3em]"
            />
            <Button
              type="submit"
              size="sm"
              variant="primary"
              isLoading={busy === "verify"}
              disabled={otpCode.length !== 6 || busy !== null}
              className="min-h-[44px]"
            >
              Verify
            </Button>
          </div>
          {devCode && (
            <span className="text-[10px] text-amber-700 block">Development server: your code is {devCode}</span>
          )}
        </form>
      )}

      {error && (
        <p role="alert" className="text-[11px] text-red-600 flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          {error}
        </p>
      )}
      <span className="text-[10px] text-charcoal-muted block">
        We text a one-time code to confirm the number. Used for urgent tenancy notifications.
      </span>
    </div>
  );
}
