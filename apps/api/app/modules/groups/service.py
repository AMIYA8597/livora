from typing import List, Optional
from uuid import UUID
from itertools import combinations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.modules.groups.models import Group, GroupMember, GroupWishlistItem
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.modules.lifestyle.models import UserDealbreaker
from app.modules.matching.engine import compute_10_dimension_compatibility, cosine_similarity
from app.modules.groups.schemas import (
    GroupCreate,
    PairwiseScoreItem,
    GroupCompatibilityResponse,
)
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException

class GroupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_groups(self, city: Optional[str] = None) -> List[Group]:
        query = (
            select(Group)
            .options(selectinload(Group.members), selectinload(Group.wishlist_items))
        )
        if city:
            query = query.where(Group.target_city.icontains(city, autoescape=True))
        result = await self.db.execute(query.order_by(Group.created_at.desc()).limit(200))
        return list(result.scalars().all())

    async def get_by_id(self, group_id: UUID) -> Optional[Group]:
        query = (
            select(Group)
            .options(selectinload(Group.members), selectinload(Group.wishlist_items))
            .where(Group.id == group_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, creator_id: UUID, data: GroupCreate) -> Group:
        group = Group(
            creator_id=creator_id,
            name=data.name,
            description=data.description,
            target_budget_total=data.target_budget_total,
            target_city=data.target_city,
            target_move_in=data.target_move_in,
        )
        self.db.add(group)
        await self.db.flush()

        leader = GroupMember(
            group_id=group.id,
            user_id=creator_id,
            role="leader",
        )
        self.db.add(leader)
        await self.db.commit()
        created = await self.get_by_id(group.id)
        if not created:
            raise NotFoundException("Group not found after creation")
        return created

    async def add_member(
        self,
        group_id: UUID,
        user_id: UUID,
        requester_id: Optional[UUID] = None,
        role: str = "member",
        is_admin: bool = False,
    ) -> GroupMember:
        group = await self.get_by_id(group_id)
        if not group:
            raise NotFoundException("Group not found")

        if role not in ("member", "leader"):
            raise BadRequestException("Role must be 'member' or 'leader'")

        # Joining yourself is open (groups are listed publicly with a Join button), but always as a
        # plain member: otherwise anyone could self-join as leader and then add arbitrary users.
        is_self_join = requester_id is not None and requester_id == user_id
        if is_self_join and requester_id != group.creator_id and not is_admin:
            role = "member"
        # Adding someone else needs the group creator, a leader, or an admin.
        elif requester_id is not None and requester_id != group.creator_id and not is_admin:
            leader_q = select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == requester_id,
                GroupMember.role == "leader"
            )
            if not (await self.db.execute(leader_q)).scalar_one_or_none():
                raise ForbiddenException("Only the group creator or a leader can add members")

        # Check existing membership
        existing_q = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        if (await self.db.execute(existing_q)).scalar_one_or_none():
            raise BadRequestException("User is already a member of this group")

        member = GroupMember(group_id=group_id, user_id=user_id, role=role)
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_member(self, group_id: UUID, user_id: UUID, requester_id: UUID, is_admin: bool = False) -> bool:
        group = await self.get_by_id(group_id)
        if not group:
            raise NotFoundException("Group not found")

        # Check permissions: requester must be group leader, admin, or removing themselves
        if requester_id != group.creator_id and requester_id != user_id and not is_admin:
            raise ForbiddenException("Permission denied to remove member")

        member_q = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        member = (await self.db.execute(member_q)).scalar_one_or_none()
        if not member:
            raise NotFoundException("Member not found in this group")

        await self.db.delete(member)
        await self.db.commit()
        return True

    async def compute_group_compatibility(self, group_id: UUID) -> GroupCompatibilityResponse:
        group = await self.get_by_id(group_id)
        if not group:
            raise NotFoundException("Group not found")

        member_ids = [m.user_id for m in group.members]
        if len(member_ids) < 2:
            return GroupCompatibilityResponse(
                group_id=group_id,
                total_members=len(member_ids),
                collective_score=100.0,
                dealbreakers_cleared=True,
                pairwise_breakdowns=[],
                group_conflicts=[],
                shared_strengths=["Group ready for candidate matching."],
            )

        # Load member profiles, users, and dealbreakers
        users_q = select(User).where(User.id.in_(member_ids))
        users_map = {u.id: u for u in (await self.db.execute(users_q)).scalars().all()}

        profs_q = select(Profile).where(Profile.user_id.in_(member_ids))
        profs_map = {p.user_id: p for p in (await self.db.execute(profs_q)).scalars().all()}

        dbs_q = select(UserDealbreaker).where(UserDealbreaker.user_id.in_(member_ids))
        all_dbs = (await self.db.execute(dbs_q)).scalars().all()
        dbs_map: dict = {}
        for d in all_dbs:
            dbs_map.setdefault(d.user_id, []).append({
                "rule_key": d.rule_key,
                "is_strict": d.is_strict,
                "expected_value": d.expected_value
            })

        pairwise_list: List[PairwiseScoreItem] = []
        scores: List[float] = []
        has_dealbreaker_conflict = False
        group_conflicts: List[str] = []

        # Evaluate all pairwise combinations
        for u1_id, u2_id in combinations(member_ids, 2):
            p1 = profs_map.get(u1_id)
            p2 = profs_map.get(u2_id)
            user1 = users_map.get(u1_id)
            user2 = users_map.get(u2_id)

            u1_name = user1.full_name if user1 else str(u1_id)
            u2_name = user2.full_name if user2 else str(u2_id)

            t1 = p1.lifestyle_traits if p1 and p1.lifestyle_traits else {}
            t2 = p2.lifestyle_traits if p2 and p2.lifestyle_traits else {}
            b1 = (p1.budget_min, p1.budget_max) if p1 else (10000, 20000)
            b2 = (p2.budget_min, p2.budget_max) if p2 else (10000, 20000)

            v1 = list(p1.lifestyle_vector) if p1 and p1.lifestyle_vector is not None else []
            v2 = list(p2.lifestyle_vector) if p2 and p2.lifestyle_vector is not None else []
            sim = cosine_similarity(v1, v2)

            comp = compute_10_dimension_compatibility(
                user_traits=t1,
                target_traits=t2,
                user_budget=b1,
                target_budget=b2,
                user_occupation=p1.occupation if p1 else None,
                target_occupation=p2.occupation if p2 else None,
                user_preferred_locs=p1.preferred_locations if p1 else [],
                target_preferred_locs=p2.preferred_locations if p2 else [],
                vector_sim=sim,
                user_dealbreakers=dbs_map.get(u1_id, []) + dbs_map.get(u2_id, []),
            )

            p_score = comp["overall_score"]
            scores.append(p_score)

            summary = None
            if not comp["dealbreakers_cleared"]:
                has_dealbreaker_conflict = True
                conflict_text = f"Severe conflict between {u1_name} and {u2_name}: {', '.join(comp['conflicts'])}"
                group_conflicts.append(conflict_text)
                summary = conflict_text

            pairwise_list.append(PairwiseScoreItem(
                user_one_id=u1_id,
                user_one_name=u1_name,
                user_two_id=u2_id,
                user_two_name=u2_name,
                score=p_score,
                dealbreakers_cleared=comp["dealbreakers_cleared"],
                conflict_summary=summary,
            ))

        avg_score = sum(scores) / len(scores) if scores else 100.0

        # Critical requirement: A high average must NOT hide one severe dealbreaker
        if has_dealbreaker_conflict:
            collective_score = round(min(avg_score * 0.5, 30.0), 1)
        else:
            collective_score = round(avg_score, 1)

        shared_strengths = ["Aligned budget ranges", "Compatible house schedules"]
        if collective_score >= 80:
            shared_strengths.append("High collective lifestyle synergy across all members.")

        return GroupCompatibilityResponse(
            group_id=group_id,
            total_members=len(member_ids),
            collective_score=collective_score,
            dealbreakers_cleared=not has_dealbreaker_conflict,
            pairwise_breakdowns=pairwise_list,
            group_conflicts=group_conflicts,
            shared_strengths=shared_strengths,
        )

    async def vote_wishlist(self, group_id: UUID, property_id: UUID, user_id: UUID, vote: str) -> GroupWishlistItem:
        # Verify user is a member of the group
        member_q = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        if not (await self.db.execute(member_q)).scalar_one_or_none():
            raise ForbiddenException("You must be an active member of this group to interact with its wishlist")

        query = select(GroupWishlistItem).where(
            GroupWishlistItem.group_id == group_id,
            GroupWishlistItem.property_id == property_id,
        )
        item = (await self.db.execute(query)).scalar_one_or_none()
        if not item:
            item = GroupWishlistItem(
                group_id=group_id,
                property_id=property_id,
                added_by=user_id,
                votes={str(user_id): vote},
            )
            self.db.add(item)
        else:
            updated_votes = dict(item.votes)
            updated_votes[str(user_id)] = vote
            item.votes = updated_votes

        await self.db.commit()
        await self.db.refresh(item)
        return item
