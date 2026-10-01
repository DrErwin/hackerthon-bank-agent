import { get } from "./api";
import type { Page } from "./contracts";

export async function getPageItems<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const result: Page<T> = await get<Page<T>>(path + (cursor ? (path.includes("?") ? "&" : "?") + "cursor=" + encodeURIComponent(cursor) : ""));
    items.push(...result.items);
    cursor = result.next_cursor;
  } while (cursor);
  return items;
}
