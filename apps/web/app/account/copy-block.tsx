"use client";

import { useState } from "react";

export function CopyBlock({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="relative mt-3">
      <pre className="font-data overflow-x-auto border border-ink/20 bg-ink p-4 text-xs text-paper">
        {text}
      </pre>
      <button
        onClick={copy}
        className="absolute top-2 right-2 border border-paper/20 px-2 py-1 text-xs text-paper hover:border-brass hover:text-brass"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
