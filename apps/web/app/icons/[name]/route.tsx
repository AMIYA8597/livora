import { ImageResponse } from "next/og";

/** PNG app icons for the manifest (Android install, splash screen) and iPhone Home Screen.
 *  "maskable" keeps the house inside the central safe zone, since Android crops it to a shape. */
const ICONS: Record<string, { size: number; glyph: number; radius: number }> = {
  "icon-192.png": { size: 192, glyph: 0.6, radius: 0.22 },
  "icon-512.png": { size: 512, glyph: 0.6, radius: 0.22 },
  "maskable-512.png": { size: 512, glyph: 0.42, radius: 0 },
  "apple-touch-icon.png": { size: 180, glyph: 0.58, radius: 0 }, // iOS rounds the corners itself
};

export function generateStaticParams() {
  return Object.keys(ICONS).map((name) => ({ name }));
}

export async function GET(_request: Request, { params }: { params: Promise<{ name: string }> }) {
  const icon = ICONS[(await params).name];
  if (!icon) return new Response("Not found", { status: 404 });
  const glyph = Math.round(icon.size * icon.glyph);
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#173D32",
          borderRadius: Math.round(icon.size * icon.radius),
        }}
      >
        <svg width={glyph} height={glyph} viewBox="10 11 20 19" fill="none">
          <path
            d="M12 21L20 13L28 21V27C28 27.5523 27.5523 28 27 28H13C12.4477 28 12 27.5523 12 27V21Z"
            stroke="white"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M17 28V22H23V28" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    ),
    { width: icon.size, height: icon.size, headers: { "Cache-Control": "public, max-age=86400" } },
  );
}
