import { useListProjectsV1ProjectsGetInfinite } from "./generated/projects/projects";

export function useInfiniteProjects(limit = 20) {
  return useListProjectsV1ProjectsGetInfinite(
    { limit, offset: 0 },
    {
      query: {
        initialPageParam: 0,
        getNextPageParam: (lastPage) =>
          lastPage.status === 200 && lastPage.data.has_more
            ? (lastPage.data.next_offset ?? undefined)
            : undefined,
      },
    },
  );
}
