type SmokeResult = {
  name: string;
  ok: boolean;
  details: string;
};

function getArg(name: string): string | undefined {
  const prefix = `--${name}=`;
  const hit = process.argv.find((arg) => arg.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : undefined;
}

async function checkHomePage(url: string): Promise<SmokeResult> {
  try {
    const response = await fetch(url);
    const html = await response.text();
    const ok = response.ok && html.includes("id=\"root\"");
    return {
      name: "Homepage serves index shell",
      ok,
      details: `status=${response.status}`,
    };
  } catch (error) {
    return {
      name: "Homepage serves index shell",
      ok: false,
      details: String(error),
    };
  }
}

async function checkHealthEndpoint(url: string): Promise<SmokeResult> {
  const healthUrl = `${url.replace(/\/$/, "")}/healthz`;
  try {
    const response = await fetch(healthUrl);
    const ok = response.status === 200 || response.status === 404;
    return {
      name: "Health endpoint check (optional)",
      ok,
      details: `status=${response.status} (404 accepted if endpoint not implemented yet)`,
    };
  } catch (error) {
    return {
      name: "Health endpoint check (optional)",
      ok: false,
      details: String(error),
    };
  }
}

async function main(): Promise<void> {
  const baseUrl = getArg("url") ?? process.env.APP_URL;
  if (!baseUrl) {
    console.error("Missing deployment URL. Use --url=https://<service-url> or set APP_URL.");
    process.exit(1);
  }

  const checks = [await checkHomePage(baseUrl), await checkHealthEndpoint(baseUrl)];
  const failed = checks.filter((item) => !item.ok);

  for (const check of checks) {
    const icon = check.ok ? "PASS" : "FAIL";
    console.log(`[${icon}] ${check.name}: ${check.details}`);
  }

  if (failed.length > 0) {
    console.error(`Smoke test failed: ${failed.length} check(s) failed.`);
    process.exit(1);
  }

  console.log("Smoke test passed.");
}

main();
