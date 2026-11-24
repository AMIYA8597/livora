import { assetLinks } from "@/lib/deep-links";

// Android App Links (see lib/deep-links.ts). Read at request time so the settings can change
// without a rebuild.
export const dynamic = "force-dynamic";

export function GET() {
  const body = assetLinks(process.env);
  if (!body) return new Response("Not found", { status: 404 });
  return Response.json(body, { headers: { "Cache-Control": "public, max-age=3600" } });
}
