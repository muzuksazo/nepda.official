// 실제 API로 보내지 않고 요청 body만 잡아 본다. 실행: npx tsx test/request-shape.ts
import { createAnthropic } from "@ai-sdk/anthropic";
import { readFileSync } from "node:fs";
import { generateScenarios } from "../src/generate.js";
import { WorkerInputSchema } from "../src/schema.js";

let body: any;
const provider = createAnthropic({
  apiKey: "test-not-a-real-key",
  fetch: async (_url, init) => {
    body = JSON.parse(String(init?.body));
    throw new Error("captured");
  },
});
const input = WorkerInputSchema.parse(JSON.parse(readFileSync("examples/01_worker-input.scenarios.json", "utf8")));
await generateScenarios(input, { model: provider("claude-opus-5-5"), modelId: "claude-opus-5-5", maxAttempts: 1 }).catch(() => {});
console.log(JSON.stringify({
  model: body.model, max_tokens: body.max_tokens, thinking: body.thinking, tool_choice: body.tool_choice,
  tools: body.tools?.length ?? 0, temperature: body.temperature,
  output_config: { effort: body.output_config?.effort, format_type: body.output_config?.format?.type },
}, null, 2));
