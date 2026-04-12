import type { StatusResponse } from "../types";

export async function fetchStatus(): Promise<StatusResponse> {
  const res = await fetch("/api/status");
  return res.json();
}
