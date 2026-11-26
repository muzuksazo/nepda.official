import { defineConfig } from "orval";

export default defineConfig({
  napda: {
    input: {
      target: "../contracts/openapi.json",
    },
    output: {
      mode: "tags-split",
      target: "src/api/generated/napdaApi.ts",
      schemas: "src/api/generated/model",
      client: "fetch",
      clean: true,
      override: {
        mutator: {
          path: "./src/api/mutator.ts",
          name: "customFetch",
        },
      },
    },
  },
});
