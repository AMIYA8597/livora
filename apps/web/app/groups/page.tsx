"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import type { GroupDTO } from "@flatmate/contracts";
import { Button, EmptyState, ErrorState, Skeleton } from "@flatmate/ui";
import { Plus, Users } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { apiClient } from "@/lib/api-client";
import { loginHref } from "@/lib/navigation";
import { InlineNotice } from "@/components/states/InlineNotice";
import { GroupCard } from "@/features/groups/components/GroupCard";
import { CreateGroupModal } from "@/features/groups/components/CreateGroupModal";
import { GroupCompatibilityModal } from "@/features/groups/components/GroupCompatibilityModal";
import { GroupWishlistModal } from "@/features/groups/components/GroupWishlistModal";
import { InviteMemberModal } from "@/features/groups/components/InviteMemberModal";

type ActiveModal =
  | { kind: "create"; nonce: number }
  | { kind: "compatibility"; group: GroupDTO }
  | { kind: "wishlist"; group: GroupDTO }
  | { kind: "invite"; group: GroupDTO }
  | null;

const GROUPS_PAGE_SIZE = 12;

export default function GroupsPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  // Wait for the session check so the request carries the token when signed in.
  const groupsQuery = useApiQuery<GroupDTO[]>(authLoading ? null : "/groups/");
  const groups = groupsQuery.data ?? [];
  const isLoading = authLoading || groupsQuery.isLoading;

  const [modal, setModal] = useState<ActiveModal>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  // Rendering every group at once is slow on phones; show a page and let people ask for more.
  const [visible, setVisible] = useState(GROUPS_PAGE_SIZE);

  /** Sign-in comes before any group action. */
  const requireAuth = (open: () => void) => {
    if (!isAuthenticated) {
      router.push(loginHref("/groups"));
      return;
    }
    open();
  };

  const membership = (groupId: string, run: () => Promise<unknown>, success: string) =>
    requireAuth(async () => {
      setBusyId(groupId);
      setNotice(null);
      try {
        await run();
        setNotice({ tone: "success", text: success });
        groupsQuery.refetch();
      } catch (err) {
        setNotice({ tone: "error", text: err instanceof Error ? err.message : "Something went wrong" });
      } finally {
        setBusyId(null);
      }
    });

  const join = (group: GroupDTO) =>
    membership(
      group.id,
      () => apiClient(`/groups/${group.id}/members`, { method: "POST", body: JSON.stringify({ user_id: user?.id, role: "member" }) }),
      `You joined ${group.name}.`,
    );

  const leave = (group: GroupDTO) =>
    membership(group.id, () => apiClient(`/groups/${group.id}/members/${user?.id}`, { method: "DELETE" }), `You left ${group.name}.`);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10 space-y-6 sm:space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-charcoal tracking-tight">Flatmate groups</h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Team up with compatible seekers to pool a budget, shortlist flats together and vote on them.
          </p>
        </div>
        {isAuthenticated && (
          <Button variant="primary" className="gap-2 w-full sm:w-auto" onClick={() => setModal({ kind: "create", nonce: Date.now() })}>
            <Plus className="w-4 h-4" />
            <span>Start a group</span>
          </Button>
        )}
      </div>

      {groupsQuery.error && (
        <ErrorState title="Couldn't load groups" message={groupsQuery.error.message} onRetry={groupsQuery.refetch} />
      )}
      {notice && <InlineNotice tone={notice.tone}>{notice.text}</InlineNotice>}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6" aria-busy="true">
          {[1, 2, 3, 4].map((n) => (
            <Skeleton key={n} variant="card" height={220} />
          ))}
        </div>
      ) : groups.length === 0 && !groupsQuery.error ? (
        <EmptyState
          icon={Users}
          title="No groups yet"
          description="Start a group to pool a budget and hunt for a flat with compatible flatmates."
          actionLabel={isAuthenticated ? "Start a group" : "Sign in to start one"}
          onAction={() => requireAuth(() => setModal({ kind: "create", nonce: Date.now() }))}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
          {groups.slice(0, visible).map((group) => (
            <GroupCard
              key={group.id}
              group={group}
              currentUserId={user?.id}
              busy={busyId === group.id}
              onJoin={() => join(group)}
              onLeave={() => leave(group)}
              onOpenWishlist={() => setModal({ kind: "wishlist", group })}
              onOpenCompatibility={() => requireAuth(() => setModal({ kind: "compatibility", group }))}
              onInvite={() => setModal({ kind: "invite", group })}
            />
          ))}
        </div>
      )}
      {!isLoading && groups.length > visible && (
        <div className="flex justify-center">
          <Button variant="secondary" onClick={() => setVisible((n) => n + GROUPS_PAGE_SIZE)}>
            Show more groups ({groups.length - visible} more)
          </Button>
        </div>
      )}

      {modal?.kind === "create" && (
        <CreateGroupModal
          key={modal.nonce}
          isOpen
          onClose={() => setModal(null)}
          onCreated={() => {
            setModal(null);
            setNotice({ tone: "success", text: "Group created. You're its leader." });
            groupsQuery.refetch();
          }}
        />
      )}
      {modal?.kind === "compatibility" && <GroupCompatibilityModal group={modal.group} onClose={() => setModal(null)} />}
      {modal?.kind === "wishlist" && (
        <GroupWishlistModal
          groupId={modal.group.id}
          currentUserId={user?.id ?? ""}
          onClose={() => setModal(null)}
          onChanged={groupsQuery.refetch}
        />
      )}
      {modal?.kind === "invite" && (
        <InviteMemberModal
          groupId={modal.group.id}
          groupName={modal.group.name}
          onClose={() => setModal(null)}
          onAdded={groupsQuery.refetch}
        />
      )}
    </div>
  );
}
