"use client";

import Image from "next/image";
import { API_BASE_URL } from "@/lib/api-client";
import { optimizable, remotePatterns } from "@/lib/image-hosts.mjs";

const PATTERNS = remotePatterns(API_BASE_URL);

interface ListingImageProps {
  src: string;
  alt: string;
  /** Responsive widths, e.g. "(max-width: 640px) 100vw, 33vw". */
  sizes: string;
  className?: string;
  /** Above-the-fold images (the first cards, the gallery's main photo) load first. */
  priority?: boolean;
}

/**
 * A listing photo filling its (positioned, sized) parent. Known hosts are resized and served as
 * AVIF/WebP by the Next.js optimizer; anything else is shown as-is rather than failing.
 */
export function ListingImage({ src, alt, sizes, className, priority = false }: ListingImageProps) {
  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes}
      className={className}
      priority={priority}
      unoptimized={!optimizable(src, PATTERNS)}
    />
  );
}
