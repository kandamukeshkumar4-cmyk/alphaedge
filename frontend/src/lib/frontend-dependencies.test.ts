import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const packageJson = JSON.parse(
  readFileSync(join(process.cwd(), "package.json"), "utf-8"),
) as { dependencies: Record<string, string> };

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
});
