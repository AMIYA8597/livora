"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Avatar, Badge, Button, Card } from "@flatmate/ui";
import { Heart, Lock, Star, ThumbsUp, XCircle } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { pricingHref, upgradeFrom, type UpgradeHint } from "@/lib/billing-model";
import { UpgradePrompt } from "@/components/billing/UpgradePrompt";

interface LikedBy {
  user_id: string;
  name: string;
  avatar_url?: string | null;
  occupation?: string | null;
  super_like: boolean;
  liked_at: string;
}

interface LikesReceived {
  count: number;
  locked: boolean;
  people: LikedBy[];
  hidden: number;
  upgrade_available: boolean;
}

/**
 * "Who liked you": everyone sees how many people are waiting for an answer; Seeker Pro sees who
 * they are and can like them back (an instant match) or pass.
 */
export function LikesReceivedPanel({ onMatched }: { onMatched?: () => void }) {
  const query = useApiQuery<LikesReceived>("/matching/likes-received");
  const [busy, setBusy] = useState<string | null>(null);
  const [hint, setHint] = useState<UpgradeHint | null>(null);
  const data = query.data;
  if (!data || data.count === 0) return null;

  const answer = async (userId: string, action: "like" | "pass") => {
    setBusy(userId);
    try {
      const res = await apiClient<{ is_mutual_match: boolean }>("/matching/interactions", {
        method: "POST",
        body: JSON.stringify({ target_user_id: userId, action }),
      });
      query.setData({
        ...data,
        count: Math.max(0, data.count - 1),
        people: data.people.filter((p) => p.user_id !== userId),
      });
      if (res.is_mutual_match) onMatched?.();
    } catch (err) {
      setHint(upgradeFrom(err) ?? { message: err instanceof Error ? err.message : "Something went wrong", plan: "", feature: "" });
    } finally {
      setBusy(null);
    }
  };

  const title = `${data.count} ${data.count === 1 ? "person likes" : "people like"} you`;

  if (data.locked) {
    return (
      <Card className="p-5 border-rose-200 bg-rose-50/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
            <Heart className="w-5 h-5 fill-rose-500" aria-hidden="true" />
          </div>
          <div>
            <h2 className="font-bold text-charcoal">{title}</h2>
            <p className="text-xs text-charcoal-muted">
              {data.upgrade_available
                ? "See who they are and match with them straight away."
                : "Keep liking people in your recommendations: if it's mutual, you'll match."}
            </p>
          </div>
        </div>
        {data.upgrade_available && (
          <Link href={pricingHref("seeker_pro")}>
            <Button variant="primary" size="sm" className="gap-1.5 min-h-[44px] md:min-h-0">
              <Lock className="w-3.5 h-3.5" aria-hidden="true" />
              <span>See who with Seeker Pro</span>
            </Button>
          </Link>
        )}
      </Card>
    );
  }

  return (
    <section aria-labelledby="likes-received-title" className="space-y-3">
      <h2 id="likes-received-title" className="font-bold text-charcoal flex items-center gap-2">
        <Heart className="w-4 h-4 text-rose-500 fill-rose-500" aria-hidden="true" />
        {title}
      </h2>
      {hint && <UpgradePrompt hint={hint} onDismiss={() => setHint(null)} />}
      <div className="grid gap-3 md:grid-cols-2">
        {data.people.map((p) => (
          <Card key={p.user_id} className="p-4 border-warm-200 bg-white flex items-center justify-between gap-3">
            <Link href={`/flatmates/${p.user_id}`} className="flex items-center gap-3 min-w-0">
              <Avatar src={p.avatar_url || undefined} alt={p.name} size="md" />
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-charcoal truncate">{p.name}</span>
                  {p.super_like && (
                    <Badge variant="warning" size="sm" className="gap-0.5">
                      <Star className="w-3 h-3" aria-hidden="true" />
                      Super like
                    </Badge>
                  )}
                </div>
                {p.occupation && <p className="text-xs text-charcoal-muted truncate">{p.occupation}</p>}
              </div>
            </Link>
            <div className="flex items-center gap-1.5 shrink-0">
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Pass on ${p.name}`}
                disabled={busy === p.user_id}
                onClick={() => answer(p.user_id, "pass")}
                className="min-h-[44px] md:min-h-0"
              >
                <XCircle className="w-4 h-4" />
              </Button>
              <Button
                variant="primary"
                size="sm"
                className="gap-1 min-h-[44px] md:min-h-0"
                isLoading={busy === p.user_id}
                onClick={() => answer(p.user_id, "like")}
              >
                <ThumbsUp className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Like back</span>
              </Button>
            </div>
          </Card>
        ))}
      </div>
      {data.hidden > 0 && (
        <p className="text-xs text-charcoal-muted">
          {data.hidden} more {data.hidden === 1 ? "keeps their" : "keep their"} profile private until you match.
        </p>
      )}
    </section>
  );
}
