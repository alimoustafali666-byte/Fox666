"use client";

import { useEffect, useState } from "react";
import { tenancyApi } from "@/lib/api-client";

// Authenticated image: the backend serves company logo bytes only to a
// signed-in member of that company (no public/signed-URL access), so it
// can't be a plain <img src="..."> -- the bytes are fetched via the
// normal authenticated API client and turned into a short-lived object
// URL, the standard technique for a Bearer-token-gated image.
export function CompanyLogo({
  hasLogo,
  size = 32,
  className,
}: {
  hasLogo: boolean;
  size?: number;
  className?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!hasLogo) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    tenancyApi
      .getLogoBlob()
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [hasLogo]);

  if (!hasLogo || !url) return null;

  return (
    // eslint-disable-next-line @next/next/no-img-element -- authenticated blob URL, not a static asset next/image can optimize
    <img
      src={url}
      alt=""
      width={size}
      height={size}
      className={className}
      style={{ borderRadius: 6, objectFit: "contain", flexShrink: 0 }}
    />
  );
}

