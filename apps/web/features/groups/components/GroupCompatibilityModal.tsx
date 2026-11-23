"use client";

import React from "react";
import type { GroupCompatibilityResponse, GroupDTO } from "@flatmate/contracts";
import { Badge, Button, Modal } from "@flatmate/ui";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { InlineNotice } from "@/components/states/InlineNotice";

interface GroupCompatibilityModalProps {
  group: GroupDTO;
  onClose: () => void;
}

export function GroupCompatibilityModal({ group, onClose }: GroupCompatibilityModalProps) {
  const { data, error, isLoading, refetch } = useApiQuery<GroupCompatibilityResponse>(`/groups/${group.id}/compatibility`);

  return (
    <Modal isOpen onClose={onClose} title={`${group.name}: compatibility`} description="How well every pair of members fits, and any dealbreakers.">
      {isLoading ? (
        <p className="py-8 text-center text-xs text-charcoal-muted" aria-busy="true">Comparing members…</p>
      ) : error ? (
        <div className="space-y-3 mt-2">
          <InlineNotice tone="error">{error.message}</InlineNotice>
          <Button variant="outline" size="sm" onClick={refetch}>Try again</Button>
        </div>
      ) : data ? (
        <div className="space-y-5 mt-2">
          <div className="flex flex-wrap items-center justify-between gap-2 p-4 bg-pale-green/30 rounded-2xl border border-brand-200">
            <div>
              <span className="text-xs font-bold text-forest uppercase tracking-wider block">Group score</span>
              <span className="text-2xl font-extrabold text-forest">{Math.round(data.collective_score)}%</span>
            </div>
            <Badge variant={data.dealbreakers_cleared ? "success" : "danger"}>
              {data.dealbreakers_cleared ? "No dealbreakers" : "Dealbreaker found"}
            </Badge>
          </div>

          {data.pairwise_breakdowns && data.pairwise_breakdowns.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-charcoal uppercase mb-2">Pairs</h3>
              <ul className="space-y-2">
                {data.pairwise_breakdowns.map((pair) => (
                  <li
                    key={`${pair.user_one_name}-${pair.user_two_name}`}
                    className="p-3 bg-warm-50 rounded-xl border border-warm-200 flex items-center justify-between gap-2 text-xs"
                  >
                    <span className="font-semibold text-charcoal min-w-0 break-words">
                      {pair.user_one_name} ↔ {pair.user_two_name}
                    </span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="font-bold text-forest">{Math.round(pair.score)}%</span>
                      {pair.dealbreakers_cleared ? (
                        <CheckCircle2 className="w-4 h-4 text-forest" aria-label="No dealbreakers" />
                      ) : (
                        <ShieldAlert className="w-4 h-4 text-rose-500" aria-label="Dealbreaker" />
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.shared_strengths && data.shared_strengths.length > 0 && (
            <section>
              <h3 className="text-xs font-bold text-charcoal uppercase mb-2">What you have in common</h3>
              <div className="flex flex-wrap gap-1.5">
                {data.shared_strengths.map((s) => (
                  <span key={s} className="px-2.5 py-1 bg-pale-green/40 text-forest border border-brand-200 text-xs rounded-lg font-semibold">
                    {s}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>
      ) : (
        <p className="py-6 text-center text-xs text-charcoal-muted">No compatibility data yet.</p>
      )}
    </Modal>
  );
}
