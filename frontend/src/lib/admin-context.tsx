"use client";

import { createContext, useContext } from "react";

const AdminKeyContext = createContext("");

export function AdminKeyProvider({
  apiKey,
  children,
}: {
  apiKey: string;
  children: React.ReactNode;
}) {
  return <AdminKeyContext.Provider value={apiKey}>{children}</AdminKeyContext.Provider>;
}

export function useAdminApiKey() {
  return useContext(AdminKeyContext);
}
