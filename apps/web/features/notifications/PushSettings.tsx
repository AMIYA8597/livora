"use client";

import React, { useEffect, useState } from "react";
import type { PushConfigDTO, PushPreferencesDTO } from "@flatmate/contracts";
import { Badge, Button, Card } from "@flatmate/ui";
import { BellRing } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useApiQuery } from "@/hooks/useApiQuery";
import { disablePush, enablePush, getPushState, type PushState } from "@/lib/push";
import { CATEGORY_LABELS } from "@/lib/notifications-model";

const STATE_TEXT: Record<PushState, string> = {
  unsupported: "This browser can't show push notifications. On iPhone or iPad, add Flatmate to your Home Screen first (Share, then Add to Home Screen) and open it from there.",
  unavailable: "Push notifications aren't switched on for Flatmate yet.",
  denied: "Notifications are blocked for this site. Allow them in your browser's site settings, then come back here.",
  off: "Get notified on this device even when Flatmate isn't open.",
  on: "This device gets push notifications.",
};

/** Turn push on or off for this browser, and choose which kinds of notification may push. */
export function PushSettings() {
  const config = useApiQuery<PushConfigDTO>("/notifications/push/config");
  const prefs = useApiQuery<PushPreferencesDTO>("/notifications/preferences");
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!config.data) return;
    let live = true;
    void getPushState(config.data).then((s) => live && setState(s));
    return () => {
      live = false;
    };
  }, [config.data]);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      setState(state === "on" ? await disablePush() : await enablePush());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't change push notifications.");
    } finally {
      setBusy(false);
    }
  };

  const setPref = async (key: keyof PushPreferencesDTO, value: boolean) => {
    const before = prefs.data;
    if (before) prefs.setData({ ...before, [key]: value });
    try {
      prefs.setData(await apiClient<PushPreferencesDTO>("/notifications/preferences", {
        method: "PUT",
        body: JSON.stringify({ [key]: value }),
      }));
    } catch (err) {
      if (before) prefs.setData(before);
      setError(err instanceof Error ? err.message : "Couldn't save that setting.");
    }
  };

  const shown = state ?? "off";
  const canToggle = state === "on" || state === "off";

  return (
    <Card className="p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <BellRing className="w-5 h-5 text-forest shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h2 className="font-bold text-charcoal flex items-center gap-2">
              Push notifications
              {state === "on" && <Badge variant="forest" size="sm">On</Badge>}
            </h2>
            <p className="text-xs text-charcoal-muted mt-0.5">{state ? STATE_TEXT[shown] : "Checking this browser…"}</p>
          </div>
        </div>
        {canToggle && (
          <Button
            variant={state === "on" ? "outline" : "primary"}
            size="sm"
            isLoading={busy}
            onClick={toggle}
            className="min-h-[44px] whitespace-nowrap"
          >
            {state === "on" ? "Turn off on this device" : "Turn on"}
          </Button>
        )}
      </div>

      {state === "on" && prefs.data && (
        <fieldset className="border-t border-slate-100 pt-3 space-y-1">
          <legend className="text-xs font-semibold text-charcoal mb-1">Send a push for</legend>
          {(Object.keys(CATEGORY_LABELS) as (keyof PushPreferencesDTO)[]).map((key) => (
            <label key={key} className="flex items-center justify-between gap-3 min-h-[44px] cursor-pointer">
              <span className="text-sm">
                <span className="font-medium text-charcoal block">{CATEGORY_LABELS[key].title}</span>
                <span className="text-[11px] text-charcoal-muted">{CATEGORY_LABELS[key].hint}</span>
              </span>
              <input
                type="checkbox"
                className="w-5 h-5 accent-forest shrink-0"
                checked={prefs.data?.[key] ?? true}
                onChange={(e) => setPref(key, e.target.checked)}
              />
            </label>
          ))}
          <p className="text-[11px] text-charcoal-muted pt-1">Everything still appears here in the app.</p>
        </fieldset>
      )}

      {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
    </Card>
  );
}
