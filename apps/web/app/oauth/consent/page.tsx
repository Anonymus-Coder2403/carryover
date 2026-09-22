import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { ConsentActions } from "./consent-actions";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function ConsentPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const authorizationId = typeof params.authorization_id === "string" ? params.authorization_id : "";

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    const qs = new URLSearchParams(
      Object.entries(params).flatMap(([k, v]) =>
        v === undefined ? [] : (Array.isArray(v) ? v : [v]).map((val) => [k, val]),
      ),
    ).toString();
    redirect(`/login?next=${encodeURIComponent(`/oauth/consent?${qs}`)}`);
  }

  if (!authorizationId) {
    return (
      <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6 py-16">
        <h1 className="font-display text-2xl font-medium">Missing request</h1>
        <p className="mt-2 text-ink/70">
          No authorization request was given. Go back to whatever app sent you here and try
          connecting again.
        </p>
      </div>
    );
  }

  const { data, error } = await supabase.auth.oauth.getAuthorizationDetails(authorizationId);

  if (error || !data) {
    return (
      <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6 py-16">
        <h1 className="font-display text-2xl font-medium">Request expired or invalid</h1>
        <p className="mt-2 text-ink/70">
          Go back to whatever app sent you here and try connecting again.
        </p>
      </div>
    );
  }

  if (!("authorization_id" in data)) {
    redirect(data.redirect_url);
  }

  const scopes = data.scope.split(" ").filter(Boolean);

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6 py-16">
      <h1 className="font-display text-2xl font-medium">Connect {data.client.name}</h1>
      <p className="mt-1 text-sm text-ink/60">Signed in as {session.user.email}</p>

      <div className="mt-6 border border-line bg-surface p-5">
        <p className="text-sm font-medium">{data.client.name} wants to</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/70">
          {scopes.length > 0 ? (
            scopes.map((s) => <li key={s}>{s}</li>)
          ) : (
            <li>access your Carryover capsules through the MCP server</li>
          )}
        </ul>
      </div>

      <ConsentActions authorizationId={data.authorization_id} />
    </div>
  );
}
