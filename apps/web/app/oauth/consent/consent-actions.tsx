"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export function ConsentActions({ authorizationId }: { authorizationId: string }) {
  const [loading, setLoading] = useState<"approve" | "deny" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function respond(action: "approve" | "deny") {
    setError(null);
    setLoading(action);
    const supabase = createClient();
    const { data, error } =
      action === "approve"
        ? await supabase.auth.oauth.approveAuthorization(authorizationId, { skipBrowserRedirect: true })
        : await supabase.auth.oauth.denyAuthorization(authorizationId, { skipBrowserRedirect: true });
    if (error || !data?.redirect_url) {
      setLoading(null);
      setError(error?.message || "Something went wrong, try again.");
      return;
    }
    window.location.href = data.redirect_url;
  }

  return (
    <div className="mt-6 flex flex-col gap-3">
      {error && <p className="text-sm text-rust">{error}</p>}
      <button
        onClick={() => respond("approve")}
        disabled={loading !== null}
        className="bg-ink px-4 py-2.5 text-sm font-medium text-surface hover:bg-brass disabled:opacity-50"
      >
        {loading === "approve" ? "Connecting..." : "Approve"}
      </button>
      <button
        onClick={() => respond("deny")}
        disabled={loading !== null}
        className="border border-line px-4 py-2.5 text-sm hover:border-ink disabled:opacity-50"
      >
        {loading === "deny" ? "Denying..." : "Deny"}
      </button>
    </div>
  );
}
