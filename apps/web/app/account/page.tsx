import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { CopyBlock } from "./copy-block";

export default async function AccountPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "https://carryover-kxq7.onrender.com";
  const token = session.access_token;
  const mcpConfig = JSON.stringify(
    {
      mcpServers: {
        carryover: {
          url: `${apiUrl}/mcp`,
          headers: { Authorization: `Bearer ${token}` },
        },
      },
    },
    null,
    2,
  );

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-6 py-16">
      <h1 className="font-display text-2xl font-medium">Account</h1>
      <p className="mt-1 text-sm text-ink/60">Signed in as {session.user.email}</p>

      <section className="mt-10 border-t border-line pt-6">
        <h2 className="font-display text-base font-medium">Bearer token</h2>
        <p className="mt-1 text-sm text-ink/70">
          Send this as <code className="font-data text-xs">Authorization: Bearer &lt;token&gt;</code> to the
          Carryover MCP server. It expires after about an hour, log in again to get a fresh one.
        </p>
        <CopyBlock text={token} />
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="font-display text-base font-medium">MCP client config</h2>
        <p className="mt-1 text-sm text-ink/70">
          Paste this into your MCP client&apos;s config to connect Carryover&apos;s
          save_capsule and load_capsule tools.
        </p>
        <CopyBlock text={mcpConfig} />
      </section>
    </div>
  );
}
