export function getBasePath(): string {
  if (typeof window === "undefined") return "/";
  return location.pathname.startsWith("/ui") ? "/ui" : "/";
}

export function toPath(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const basePath = getBasePath();
  if (basePath === "/") return normalized;
  if (normalized === "/") return `${basePath}/`;
  return `${basePath}${normalized}`;
}
