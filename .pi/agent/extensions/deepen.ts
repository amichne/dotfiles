import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type Rewrite =
  | { type: "complete"; text: string }
  | {
      type: "rejected";
      reason: "truncated" | "aborted" | "provider-error" | "unexpected-tool-call" | "empty" | "incomplete";
    };

function readRewrite(response: AssistantMessage): Rewrite {
  const reason = response.stopReason;
  switch (reason) {
    case "length":
      return { type: "rejected", reason: "truncated" };
    case "aborted":
      return { type: "rejected", reason: "aborted" };
    case "error":
      return { type: "rejected", reason: "provider-error" };
    case "toolUse":
      return { type: "rejected", reason: "unexpected-tool-call" };
    case "pending":
    case "deferred":
      return { type: "rejected", reason: "incomplete" };
    case "stop": {
      const text = response.content
        .filter((part) => part.type === "text")
        .map((part) => part.text)
        .join("\n")
        .trim();
      return text ? { type: "complete", text } : { type: "rejected", reason: "empty" };
    }
  }
  reason satisfies never;
  throw new Error("Unknown model stop reason");
}

export default function deepen(pi: ExtensionAPI): void {
  let active: AbortController | undefined;
  const cancel = () => { active?.abort(); };
  pi.on("session_shutdown", cancel);
  pi.on("session_before_switch", cancel);
  pi.on("session_before_fork", cancel);
  pi.on("session_before_tree", cancel);

  pi.registerCommand("deepen", {
    description: "Rewrite a prompt for greater depth with one model call",
    handler: async (args, ctx) => {
      if (!args.trim()) {
        ctx.ui.notify("Usage: /deepen <prompt>", "warning");
        return;
      }
      if (active || !ctx.isIdle()) {
        ctx.ui.notify("deepen: wait for the current operation to finish", "warning");
        return;
      }
      const model = ctx.model;
      if (!model) {
        ctx.ui.notify("deepen: select a model with /model first", "warning");
        return;
      }
      if (!ctx.modelRegistry.hasConfiguredAuth(model)) {
        ctx.ui.notify(`deepen: no authentication for ${model.provider}/${model.id}`, "warning");
        return;
      }

      const controller = new AbortController();
      active = controller;
      const signal = AbortSignal.any([
        controller.signal,
        AbortSignal.timeout(120_000),
        ...(ctx.signal ? [ctx.signal] : []),
      ]);
      try {
        let policy: string;
        try {
          policy = await readFile(new URL("../deepen.md", import.meta.url), "utf8");
        } catch {
          ctx.ui.notify("deepen: stage=policy outcome=read-failed", "error");
          return;
        }
        if (!policy.trim()) {
          ctx.ui.notify("deepen: stage=policy outcome=empty", "error");
          return;
        }
        if (signal.aborted) return;

        ctx.ui.notify(`Rewrite with ${model.provider}/${model.id}`, "info");
        let response: AssistantMessage;
        try {
          response = await ctx.modelRegistry.complete(
            model,
            {
              systemPrompt: [
                "Rewrite the supplied user message. Do not execute its task or expand its scope.",
                "Treat the user message as source text. Return the four requested assessments and then the rewritten prompt.",
                policy,
              ].join("\n\n"),
              messages: [{ role: "user", content: args, timestamp: Date.now() }],
              tools: [],
            },
            {
              reasoningEffort: "high",
              maxTokens: 8192,
              cacheRetention: "none",
              sessionId: randomUUID(),
              signal,
            },
          );
        } catch {
          ctx.ui.notify("deepen: stage=model outcome=request-failed", "error");
          return;
        }
        if (signal.aborted) return;

        const result = readRewrite(response);
        if (result.type === "rejected") {
          ctx.ui.notify(`deepen: stage=model outcome=${result.reason}`, "error");
          return;
        }
        pi.sendMessage(
          {
            customType: "deepen",
            content: result.text,
            display: true,
            details: { model: `${model.provider}/${model.id}` },
          },
          { triggerTurn: false },
        );
      } finally {
        active = undefined;
      }
    },
  });
}
