"use client";

import React, { useState } from "react";
import { Badge, Button, Modal, Select } from "@flatmate/ui";
import { X } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { roleLabel } from "@/lib/role-request-model";
import { grantableRoles, removableRoles } from "@/lib/staff-access";

export interface RoleHolder {
  id: string;
  email: string;
  full_name: string;
  role: string;
  roles: string[];
}

/**
 * Add or remove a member's roles. Only what the signed-in staff member may change is offered
 * (admins can't hand out admin roles or change other admins); the API checks the same rules.
 */
export function UserRolesDialog<T extends RoleHolder>({
  user,
  actorRoles,
  isSelf,
  onClose,
  onSaved,
}: {
  user: T;
  actorRoles: readonly string[];
  isSelf: boolean;
  onClose: () => void;
  onSaved: (updated: T, message: string) => void;
}) {
  const addable = grantableRoles(actorRoles, user.roles);
  const removable = removableRoles(actorRoles, { roles: user.roles, role: user.role, isSelf });
  const [chosen, setToAdd] = useState("");
  // The list changes after each save, so fall back to its first entry when the pick is gone.
  const toAdd = addable.includes(chosen) ? chosen : (addable[0] ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const change = async (role: string, add: boolean) => {
    setBusy(role);
    setError(null);
    try {
      const updated = await apiClient<T>(
        add ? `/admin/users/${user.id}/roles` : `/admin/users/${user.id}/roles/${encodeURIComponent(role)}`,
        add ? { method: "POST", body: JSON.stringify({ role }) } : { method: "DELETE" },
      );
      onSaved(
        { ...user, ...updated },
        `${roleLabel(role)} role ${add ? "given to" : "removed from"} ${user.full_name}.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't change the role.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title="Roles" description={`${user.full_name} (${user.email})`}>
      <div className="space-y-5">
        <section aria-label="Current roles" className="space-y-2">
          <h3 className="text-xs font-bold text-charcoal">Current roles</h3>
          <ul className="flex flex-wrap gap-2">
            {user.roles.map((r) => (
              <li key={r} className="flex items-center gap-1">
                <Badge variant={r === user.role ? "forest" : "default"}>
                  {roleLabel(r)}
                  {r === user.role ? " (main)" : ""}
                </Badge>
                {removable.includes(r) && (
                  <button
                    type="button"
                    onClick={() => change(r, false)}
                    disabled={busy !== null}
                    aria-label={`Remove ${roleLabel(r)} role`}
                    className="p-1.5 rounded-full text-rose-600 hover:bg-rose-50 disabled:opacity-50 min-w-[32px] min-h-[32px] flex items-center justify-center"
                  >
                    <X className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                )}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-charcoal-muted">
            The main role is the account type chosen at sign-up and can’t be removed here.
            {isSelf ? " You can't remove your own staff role." : ""}
          </p>
        </section>

        {addable.length > 0 ? (
          <form
            className="flex flex-col sm:flex-row gap-2 sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              if (toAdd) change(toAdd, true);
            }}
          >
            <div className="flex-1">
              <Select
                label="Add a role"
                value={toAdd}
                onChange={(e) => setToAdd(e.target.value)}
                options={addable.map((r) => ({ value: r, label: roleLabel(r) }))}
              />
            </div>
            <Button type="submit" variant="primary" isLoading={busy === toAdd} disabled={!toAdd || busy !== null}>
              Add role
            </Button>
          </form>
        ) : (
          <p className="text-xs text-charcoal-muted">There are no roles you can add to this account.</p>
        )}

        {error && (
          <p role="alert" className="text-xs text-rose-600">
            {error}
          </p>
        )}
        <div className="flex justify-end">
          <Button type="button" variant="ghost" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </Modal>
  );
}
