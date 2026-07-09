import { redirect } from "next/navigation";

// Discover is the home shell (`/`). Keep this route as an alias.
export default function DiscoverRedirect() {
  redirect("/");
}
