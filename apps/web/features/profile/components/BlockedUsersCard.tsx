"use client";

import React, { useState } from "react";
import { Button, Card } from "@flatmate/ui";
import { Ban, UserX } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useApiQuery } from "@/hooks/useApiQuery";
import { InlineNotice } from "@/components/states/InlineNotice";

interface BlockedUser {
  id: string;
  blocked_user_id: string;
  created_at: string;
}

export function BlockedUsersCard() {
  const query = useApiQuery<BlockedUser[]>("/moderation/blocks");
  const blocked = query.data ?? [];
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUnblock = async (blockedUserId: string) => {
    setBusy(blockedUserId);
    setError(null);
    try {
      await apiClient(`/moderation/blocks/${blockedUserId}`, { method: "DELETE" });
      query.setData((prev = []) => prev.filter((b) => b.blocked_user_id !== blockedUserId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unblock user");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-base font-bold text-charcoal">Blocked users ({blocked.length})</h3>
        <Ban className="w-4 h-4 text-rose-500" />
      </div>
      <p className="text-xs text-charcoal-muted mb-4">
        Blocked users cannot message you, view your full profile or send match requests.
      </p>
      {error && <InlineNotice tone="error" className="mb-3">{error}</InlineNotice>}
      {query.isLoading ? (
        <div className="h-12 bg-slate-100 rounded-xl animate-pulse" />
      ) : query.error ? (
        <InlineNotice tone="error">Couldn&apos;t load blocked users. {query.error.message}</InlineNotice>
      ) : blocked.length === 0 ? (
        <p className="text-xs text-charcoal-muted italic py-2">No users currently blocked.</p>
      ) : (
        <div className="space-y-2">
          {blocked.map((b) => (
            <div key={b.id} className="p-3 bg-warm rounded-xl border border-slate-200 flex items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <UserX className="w-4 h-4 text-rose-500" />
                <span className="text-charcoal font-medium">User #{b.blocked_user_id.slice(0, 8)}</span>
              </div>
              <Button size="sm" variant="outline" isLoading={busy === b.blocked_user_id} onClick={() => handleUnblock(b.blocked_user_id)} className="min-h-[44px]">
                Unblock
              </Button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
