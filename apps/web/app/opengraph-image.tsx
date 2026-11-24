import { ImageResponse } from "next/og";

// The default link-preview image for pages without their own (listings use their first photo).
export const alt = "Flatmate: find your place, find your people";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#173D32",
          color: "#FFFFFF",
        }}
      >
        <div style={{ fontSize: 44, fontWeight: 700, opacity: 0.85 }}>flatmate.</div>
        <div style={{ fontSize: 76, fontWeight: 800, lineHeight: 1.1, marginTop: 28 }}>
          Find your place. Find your people.
        </div>
        <div style={{ fontSize: 34, marginTop: 28, opacity: 0.85 }}>
          Verified rooms, flats and PGs, and flatmates matched on how you live.
        </div>
      </div>
    ),
    size,
  );
}
