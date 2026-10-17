export {};

type Parsed<T> = { kind: "accepted"; value: T } | {
  kind: "rejected";
  reason: "invalid_config" | "invalid_request";
};

type TimeoutPolicy = "insufficient_evidence" | "model_judgment";

interface Question {
  readonly id: string;
  readonly prompt: string;
  readonly options: readonly string[];
  readonly timeoutMs: number;
  readonly onTimeout: TimeoutPolicy;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, limit: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= limit;
}

function duration(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1 && value <= 3_600_000;
}

/** The private constructor admits only a complete, bounded, independent question batch. */
export class QuestionBatch {
  readonly #questions: readonly [Question, ...Question[]];

  private constructor(questions: readonly [Question, ...Question[]]) {
    this.#questions = questions;
  }

  get questions(): readonly [Question, ...Question[]] {
    return this.#questions;
  }

  static parse(input: unknown, config: unknown): Parsed<QuestionBatch> {
    if (!record(config) || Object.keys(config).some(key => key !== "defaultTimeoutMs") ||
        !duration(config.defaultTimeoutMs)) {
      return { kind: "rejected", reason: "invalid_config" };
    }
    if (!record(input) || Object.keys(input).some(key => key !== "questions") ||
        !Array.isArray(input.questions) || input.questions.length < 1 || input.questions.length > 5) {
      return { kind: "rejected", reason: "invalid_request" };
    }
    const questions: Question[] = [];
    const ids = new Set<string>();
    for (const item of input.questions) {
      if (!record(item) || Object.keys(item).some(key =>
        !["id", "prompt", "options", "timeoutMs", "onTimeout"].includes(key))) {
        return { kind: "rejected", reason: "invalid_request" };
      }
      const timeoutMs = item.timeoutMs === undefined ? config.defaultTimeoutMs : item.timeoutMs;
      const onTimeout = item.onTimeout === undefined ? "insufficient_evidence" : item.onTimeout;
      const options = item.options === undefined ? [] : item.options;
      if (!text(item.id, 64) || !text(item.prompt, 4096) || !duration(timeoutMs) ||
          (onTimeout !== "insufficient_evidence" && onTimeout !== "model_judgment") ||
          !Array.isArray(options) || options.length > 8 ||
          !options.every((option: unknown): option is string => text(option, 256))) {
        return { kind: "rejected", reason: "invalid_request" };
      }
      const id = item.id.trim();
      const labels = options.map(option => option.trim());
      if (ids.has(id) || new Set(labels).size !== labels.length) {
        return { kind: "rejected", reason: "invalid_request" };
      }
      ids.add(id);
      questions.push(Object.freeze({ id, prompt: item.prompt.trim(), options: Object.freeze(labels), timeoutMs, onTimeout }));
    }
    const [head, ...tail] = questions;
    if (head === undefined) return { kind: "rejected", reason: "invalid_request" };
    return { kind: "accepted", value: new QuestionBatch(Object.freeze([head, ...tail])) };
  }
}

export type QuestionOutcome =
  | { id: string; status: "answered"; answer: { kind: "selection" | "freeform"; text: string } }
  | { id: string; status: "timed_out"; next: TimeoutPolicy }
  | { id: string; status: "cancelled" | "aborted" | "not_asked" | "ui_error" | "invalid_answer" };

export interface DialogHost {
  select(title: string, options: string[], signal: AbortSignal, timeoutMs: number): Promise<string | undefined>;
  input(title: string, signal: AbortSignal, timeoutMs: number): Promise<string | undefined>;
}

export interface Clock {
  now(): number;
  schedule(callback: () => void, delayMs: number): () => void;
}

function askOne(question: Question, host: DialogHost, clock: Clock, parent: AbortSignal): Promise<QuestionOutcome> {
  return new Promise(resolve => {
    const controller = new AbortController();
    const deadline = clock.now() + question.timeoutMs;
    let settled = false;
    let stopTimer = () => {};
    const finish = (outcome: QuestionOutcome) => {
      if (settled) return;
      settled = true;
      stopTimer();
      parent.removeEventListener("abort", abort);
      controller.abort();
      resolve(outcome);
    };
    const timeout = () => finish({ id: question.id, status: "timed_out", next: question.onTimeout });
    const abort = () => finish({ id: question.id, status: "aborted" });
    parent.addEventListener("abort", abort, { once: true });
    if (parent.aborted) {
      abort();
      return;
    }
    stopTimer = clock.schedule(timeout, question.timeoutMs);
    const remaining = () => Math.max(1, deadline - clock.now());
    const other = "Type a response…";
    const show = async (): Promise<QuestionOutcome> => {
      let answer: string | undefined;
      let kind: "selection" | "freeform" = "freeform";
      if (question.options.length > 0) {
        const labels = question.options.map((option, index) => `${index + 1}. ${option}`);
        const selected = await host.select(question.prompt, [...labels, other], controller.signal, remaining());
        if (settled) return { id: question.id, status: "not_asked" };
        if (selected === other) {
          answer = await host.input(question.prompt, controller.signal, remaining());
        } else if (selected !== undefined) {
          const index = labels.indexOf(selected);
          if (index < 0) return { id: question.id, status: "invalid_answer" };
          answer = question.options[index];
          kind = "selection";
        }
      } else {
        answer = await host.input(question.prompt, controller.signal, remaining());
      }
      if (answer === undefined) return { id: question.id, status: "cancelled" };
      if (answer.trim().length === 0) return { id: question.id, status: "invalid_answer" };
      return { id: question.id, status: "answered", answer: { kind, text: answer.trim() } };
    };
    const complete = (outcome: QuestionOutcome) => {
      if (parent.aborted) abort();
      else if (clock.now() >= deadline) timeout();
      else finish(outcome);
    };
    void show().then(complete, () => complete({ id: question.id, status: "ui_error" }));
  });
}

/** A later round is a new invocation. No pending answer or timer crosses rounds. */
export async function askBatch(batch: QuestionBatch, host: DialogHost, clock: Clock, signal: AbortSignal): Promise<QuestionOutcome[]> {
  const outcomes: QuestionOutcome[] = [];
  let stopped = false;
  for (const question of batch.questions) {
    if (stopped) {
      outcomes.push({ id: question.id, status: "not_asked" });
      continue;
    }
    const outcome = await askOne(question, host, clock, signal);
    outcomes.push(outcome);
    stopped = outcome.status !== "answered" && outcome.status !== "timed_out";
  }
  return outcomes;
}
