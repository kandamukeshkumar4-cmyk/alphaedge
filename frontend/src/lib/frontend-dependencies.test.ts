import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const packageJson = JSON.parse(
  readFileSync(join(process.cwd(), "package.json"), "utf-8"),
) as {
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
  overrides?: Record<string, string | Record<string, string>>;
};

const packageLock = JSON.parse(
  readFileSync(join(process.cwd(), "package-lock.json"), "utf-8"),
) as {
  packages: Record<
    string,
    {
      version?: string;
      deprecated?: string;
      dependencies?: Record<string, string>;
    }
  >;
};

function isAtLeast(version: string | undefined, minimum: string): boolean {
  if (!version) {
    return false;
  }

  const currentParts = version.split(".").map((part) => Number.parseInt(part, 10));
  const minimumParts = minimum.split(".").map((part) => Number.parseInt(part, 10));

  for (let index = 0; index < minimumParts.length; index += 1) {
    const currentPart = currentParts[index] ?? 0;
    const minimumPart = minimumParts[index] ?? 0;

    if (currentPart > minimumPart) {
      return true;
    }

    if (currentPart < minimumPart) {
      return false;
    }
  }

  return true;
}

describe("frontend dependency contract", () => {
  it("uses Recharts 3+ without deprecated 2.x transitive packages", () => {
    const declaredRange = packageJson.dependencies.recharts;
    const lockedRecharts = packageLock.packages["node_modules/recharts"];

    expect(declaredRange).toMatch(/^\^3\./);
    expect(lockedRecharts.version).toMatch(/^3\./);
    expect(lockedRecharts.deprecated).toBeUndefined();
    expect(lockedRecharts.dependencies).not.toHaveProperty("recharts-scale");
    expect(packageLock.packages).not.toHaveProperty("node_modules/recharts-scale");
  });

  it("keeps Next's bundled PostCSS at the patched advisory floor", () => {
    const rootPostcss = packageLock.packages["node_modules/postcss"];
    const nextPostcss = packageLock.packages["node_modules/next/node_modules/postcss"];

    expect(packageJson.overrides).toMatchObject({
      postcss: "$postcss",
    });
    expect(packageJson.devDependencies.postcss).toBe("^8.5.15");
    expect(isAtLeast(rootPostcss.version, "8.5.10")).toBe(true);

    if (nextPostcss) {
      expect(isAtLeast(nextPostcss.version, "8.5.10")).toBe(true);
    }
  });
});
