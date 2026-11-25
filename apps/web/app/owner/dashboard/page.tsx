import { redirect } from "next/navigation";

// The listings dashboard lives at /owner; this older address only forwards there.
export default function OwnerDashboardRedirect(): never {
  redirect("/owner");
}
