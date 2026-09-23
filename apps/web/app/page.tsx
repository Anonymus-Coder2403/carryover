import Link from "next/link";
import { Gauge } from "./gauge";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-6">
        <span className="font-display text-lg font-semibold tracking-tight">Carryover</span>
        <nav className="flex items-center gap-5 text-sm">
          <Link href="/login" className="text-ink/60 hover:text-ink">
            Log in
          </Link>
          <Link
            href="/signup"
            className="border border-ink px-3 py-1.5 text-ink hover:border-brass hover:text-brass"
          >
            Sign up
          </Link>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-14">
        <div className="grid items-center gap-10 sm:grid-cols-[1.2fr_1fr]">
          <div>
            <h1 className="font-display max-w-xl text-4xl leading-[1.1] font-medium tracking-tight text-balance sm:text-5xl">
              Your AI gets measurably worse before it runs out of room.
            </h1>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-ink/70">
              Carryover tells you when to move, and moves the thinking for you. It turns a
              dying chat session into a portable context capsule, then rehydrates it into a
              fresh session in Claude, ChatGPT or Cursor.
            </p>
            <Link
              href="/signup"
              className="mt-8 inline-block border border-ink px-5 py-2.5 text-sm font-medium hover:border-brass hover:text-brass"
            >
              Create an account
            </Link>
          </div>
          <Gauge />
        </div>

        <div className="mt-16 grid divide-y divide-line border-t border-b border-line text-sm sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="py-6 sm:pr-8 sm:py-8">
            <h2 className="font-display text-base font-medium">Compress</h2>
            <p className="mt-2 leading-relaxed text-ink/70">
              One model call turns a transcript into a capsule: decisions made, approaches
              already ruled out, constraints that still apply, and exactly where the work
              stands.
            </p>
          </div>
          <div className="py-6 sm:px-8 sm:py-8">
            <h2 className="font-display text-base font-medium">Rehydrate</h2>
            <p className="mt-2 leading-relaxed text-ink/70">
              The same capsule renders as a resume prompt in three dialects, so the next
              session picks up without explaining anything again.
            </p>
          </div>
          <div className="py-6 sm:pl-8 sm:py-8">
            <h2 className="font-display text-base font-medium">Verify</h2>
            <p className="mt-2 leading-relaxed text-ink/70">
              A fidelity check answers questions from the original transcript using only the
              capsule, so a handoff is a number on screen, not a guess.
            </p>
          </div>
        </div>

        <div className="mt-12 border border-brass/40 bg-surface p-7">
          <h2 className="font-display text-lg font-medium">Use it from an AI assistant over MCP</h2>
          <p className="mt-2 max-w-2xl leading-relaxed text-ink/70">
            Carryover also runs as an MCP server, so an assistant can save and load capsules
            for you directly. Sign in to get the bearer token and connection details for
            your MCP client.
          </p>
          <Link
            href="/signup"
            className="mt-5 inline-block bg-ink px-5 py-2.5 text-sm font-medium text-surface hover:bg-brass"
          >
            Create an account
          </Link>
        </div>
      </main>

      <footer className="mx-auto w-full max-w-4xl px-6 py-8 text-sm text-ink/40">
        Built at the Airtribe x Render Ship Room hackathon, Bengaluru.
      </footer>
    </div>
  );
}
