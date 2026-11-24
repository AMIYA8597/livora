import { appleAppSiteAssociation } from "@/lib/deep-links";

// iOS Universal Links and password autofill (see lib/deep-links.ts). Apple fetches this without
// redirects and needs application/json even though the name has no extension.
export const dynamic = "force-dynamic";

export function GET() {
  const body = appleAppSiteAssociation(process.env);
  if (!body) return new Response("Not found", { status: 404 });
  return Response.json(body, { headers: { "Cache-Control": "public, max-age=3600" } });
}
