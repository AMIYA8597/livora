"use client";

import React, { useState } from "react";
import type { DealbreakerDTO } from "@flatmate/contracts";
import { Badge, Button, Card } from "@flatmate/ui";
import { Plus, Shield, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";
import { DEALBREAKER_RULES, dealbreakerLabel } from "../lifestyle-options";

interface DealbreakersPanelProps {
  items: DealbreakerDTO[];
  onAdded: (item: DealbreakerDTO) => void;
  onRemoved: (id: string) => void;
}

/** Hard constraints that exclude or flag incompatible flatmates. */
export function DealbreakersPanel({ items, onAdded, onRemoved }: DealbreakersPanelProps) {
  const available = DEALBREAKER_RULES.filter((r) => !items.some((d) => d.rule_key === r.value));
  const [rule, setRule] = useState(available[0]?.value ?? "");
  const [isStrict, setIsStrict] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedRule = available.some((r) => r.value === rule) ? rule : available[0]?.value ?? "";

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const def = DEALBREAKER_RULES.find((r) => r.value === selectedRule);
    if (!def) return;
    setBusy("add");
    setError(null);
    try {
      const created = await apiClient<DealbreakerDTO>("/lifestyle/dealbreakers", {
        method: "POST",
        body: JSON.stringify({ rule_key: def.value, is_strict: isStrict, expected_value: def.expected }),
      });
      onAdded(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add dealbreaker");
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      await apiClient(`/lifestyle/dealbreakers/${id}`, { method: "DELETE" });
      onRemoved(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove dealbreaker");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="p-6 max-w-3xl">
      <div className="mb-5">
        <h2 className="text-lg font-bold text-charcoal">Dealbreakers</h2>
        <p className="text-xs text-charcoal-muted mt-1">
          Strict rules exclude anyone who breaks them; others lower the match score.
        </p>
      </div>

      {error && <InlineNotice tone="error" className="mb-4">{error}</InlineNotice>}

      {available.length > 0 ? (
        <form onSubmit={handleAdd} className="bg-warm p-4 rounded-xl border border-slate-200/80 mb-6 flex flex-col sm:flex-row sm:flex-wrap gap-3 sm:items-end">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="db-rule" className="block text-xs font-semibold text-charcoal mb-1">Rule</label>
            <select
              id="db-rule"
              value={selectedRule}
              onChange={(e) => setRule(e.target.value)}
              className="w-full min-h-[44px] text-sm rounded-xl border border-slate-200 px-2.5 bg-white"
            >
              {available.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
          <label htmlFor="db-strict" className="flex items-center gap-2 min-h-[44px] px-3 bg-white border border-slate-200 rounded-xl text-xs font-semibold text-charcoal">
            <input
              id="db-strict"
              type="checkbox"
              checked={isStrict}
              onChange={(e) => setIsStrict(e.target.checked)}
              className="h-4 w-4 rounded accent-forest"
            />
            Strict (exclude matches)
          </label>
          <Button type="submit" variant="primary" isLoading={busy === "add"} className="min-h-[44px]">
            <Plus className="w-3.5 h-3.5 mr-1" /> Add rule
          </Button>
        </form>
      ) : (
        <p className="text-xs text-charcoal-muted mb-6">All available dealbreakers are active.</p>
      )}

      <div className="space-y-2">
        <h3 className="text-xs font-bold text-charcoal-muted uppercase">Active ({items.length})</h3>
        {items.length === 0 ? (
          <p className="text-xs text-charcoal-muted py-4 text-center">No dealbreakers yet.</p>
        ) : (
          items.map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-2 p-3 bg-white rounded-xl border border-slate-200">
              <div className="flex items-center gap-2 min-w-0">
                <Shield className="w-4 h-4 text-rose-500 shrink-0" />
                <span className="text-sm font-semibold text-charcoal truncate">{dealbreakerLabel(d.rule_key)}</span>
                {d.is_strict && <Badge variant="danger" size="sm">Strict</Badge>}
              </div>
              <button
                type="button"
                onClick={() => handleDelete(d.id)}
                disabled={busy === d.id}
                aria-label={`Remove ${dealbreakerLabel(d.rule_key)}`}
                className="min-w-[44px] min-h-[44px] flex items-center justify-center text-slate-400 hover:text-rose-600 disabled:opacity-50 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
