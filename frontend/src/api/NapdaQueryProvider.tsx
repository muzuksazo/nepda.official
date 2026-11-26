import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { napdaQueryClient } from "./queryClient";

export interface NapdaQueryProviderProps {
  children: ReactNode;
}

export function NapdaQueryProvider({ children }: NapdaQueryProviderProps) {
  return (
    <QueryClientProvider client={napdaQueryClient}>
      {children}
    </QueryClientProvider>
  );
}
