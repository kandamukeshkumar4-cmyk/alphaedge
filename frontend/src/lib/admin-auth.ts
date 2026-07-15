export function adminHeaders(apiKey: string): HeadersInit {
  return {
    "X-Admin-API-Key": apiKey,
  };
}
