import { readFile } from "node:fs/promises";
import type { AgentToolResult, ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { askBatch, QuestionBatch, type QuestionOutcome } from "../lib/questions.ts";

const Parameters = Type.Object({
  questions: Type.Array(Type.Object({
    id: Type.String({ minLength: 1, maxLength: 64 }),
    prompt: Type.String({ minLength: 1, maxLength: 4096 }),
    options: Type.Optional(Type.Array(Type.String({ minLength: 1, maxLength: 256 }), { maxItems: 8, uniqueItems: true })),
    timeoutMs: Type.Optional(Type.Integer({ minimum: 1, maximum: 3_600_000 })),
    onTimeout: Type.Optional(Type.Union([Type.Literal("insufficient_evidence"), Type.Literal("model_judgment")])),
  }, { additionalProperties: false }), { minItems: 1, maxItems: 5 }),
}, { additionalProperties: false });

type Failure = "ui_unavailable" | "busy" | "config_unavailable" | "invalid_config" | "invalid_request";
type Details = { status: Failure } | { toolCallId: string; outcomes: QuestionOutcome[] };

function failure(reason: Failure): AgentToolResult<Details> {
  return { isError: true, content: [{ type: "text", text: `ask_questions: ${reason}` }], details: { status: reason } };
}

export default function register(pi: ExtensionAPI) {
  let active: AbortController | undefined;
  const cancel = () => active?.abort();
  pi.on("session_shutdown", cancel);
  pi.on("session_before_switch", cancel);
  pi.on("session_before_fork", cancel);
  pi.on("session_before_tree", cancel);

  pi.registerTool<typeof Parameters, Details>({
    name: "ask_questions",
    label: "Ask questions",
    description: "Ask 1–5 independent questions in order. Each question has its own response deadline, which starts when displayed. Returns user answers or explicit unanswered outcomes.",
    promptSnippet: "Ask timed questions with a separate deadline and timeout policy for each question",
    promptGuidelines: [
      "Ask dependent questions in a later call after you examine the earlier answers.",
      "A timeout is not consent or a user answer. Cancellation and errors never permit a guess.",
      "Use insufficient_evidence when a missing answer blocks safe work. Continue only independent work.",
      "Use model_judgment only for reversible choices within existing authority. After timeout, examine the evidence again and either state a provisional choice with its evidence or veto the guess as insufficient evidence. You can always veto a guess.",
      "Never infer permission for publication, installation, deletion, credentials, spending, or an irreversible choice from silence.",
      "A child without a user interface must contact its supervisor for questions. Do not treat ui_unavailable as a timeout.",
    ],
    parameters: Parameters,
    executionMode: "sequential",
    async execute(toolCallId, input, signal, _update, ctx) {
      if (!ctx.hasUI) return failure("ui_unavailable");
      if (active) return failure("busy");
      const controller = new AbortController();
      active = controller;
      try {
        let config: unknown;
        try {
          config = JSON.parse(await readFile(new URL("../questions.json", import.meta.url), "utf8"));
        } catch (error) {
          return failure(error instanceof SyntaxError ? "invalid_config" : "config_unavailable");
        }
        const parsed = QuestionBatch.parse(input, config);
        if (parsed.kind === "rejected") return failure(parsed.reason);
        const combined = signal ? AbortSignal.any([controller.signal, signal]) : controller.signal;
        const outcomes = await askBatch(parsed.value, {
          select: (title, options, questionSignal, timeout) => ctx.ui.select(
            `${title}\nResponse window: ${Math.ceil(timeout / 1000)}s`, options, { signal: questionSignal }),
          input: (title, questionSignal, timeout) => ctx.ui.input(
            `${title}\nResponse window: ${Math.ceil(timeout / 1000)}s`, undefined, { signal: questionSignal }),
        }, {
          now: () => performance.now(),
          schedule: (callback, delay) => {
            const timer = setTimeout(callback, delay);
            return () => clearTimeout(timer);
          },
        }, combined);
        const details = { toolCallId, outcomes };
        const isError = outcomes.some(outcome => outcome.status === "ui_error" || outcome.status === "invalid_answer");
        return { isError, content: [{ type: "text", text: JSON.stringify(details) }], details };
      } finally {
        controller.abort();
        if (active === controller) active = undefined;
      }
    },
  });
}
