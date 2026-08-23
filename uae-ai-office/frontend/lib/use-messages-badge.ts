"use client";

import { useEffect, useState } from "react";
import { collaborationApi } from "./api-client";
import { useAuth } from "./auth-context";

const POLL_INTERVAL_MS = 25_000;

// Drives the small unread-count badge on the sidebar's Messages nav
// item. Deliberately independent of CollaborationProvider (which only
// mounts inside /messages) so the badge stays live from anywhere in the
// app -- a single cheap notifications call, not the full conversation
// list.
export function useMessagesUnreadBadge(): number {
  const { status } = useAuth();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (status !== "authenticated") {
      setUnread(0);
      return;
    }
    let cancelled = false;

    async function poll() {
      try {
        const page = await collaborationApi.listNotifications({ unread_only: true, limit: 1 });
        if (!cancelled) setUnread(page.unread_count);
      } catch {
        // Silently skip -- a stale/missing badge is not worth surfacing an error for.
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [status]);

  return unread;
}

