import type { ReactionEmoji } from "@/lib/types";

// Visual glyph for each allowlisted reaction identifier (see
// backend/app/modules/collaboration/service.py's ALLOWED_REACTIONS) --
// the identifier itself is what's sent to the API and stored, this is
// purely a client-side display concern.
export const REACTION_GLYPHS: Record<ReactionEmoji, string> = {
  thumbsup: "👍",
  thumbsdown: "👎",
  heart: "❤️",
  laugh: "😂",
  surprised: "😮",
  sad: "😢",
  pray: "🙏",
  party: "🎉",
};

