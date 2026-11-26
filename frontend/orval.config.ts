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
      client: "react-query",
      httpClient: "fetch",
      clean: true,
      override: {
        mutator: {
          path: "./src/api/mutator.ts",
          name: "customFetch",
        },
        query: {
          signal: true,
          version: 5,
        },
        operations: {
          list_projects_v1_projects_get: {
            query: {
              useQuery: true,
              useInfinite: true,
              useInfiniteQueryParam: "offset",
            },
          },
          list_jobs_v1_jobs_get: {
            query: {
              useQuery: true,
              useInfinite: true,
              useInfiniteQueryParam: "offset",
            },
          },
        },
      },
    },
  },
});
