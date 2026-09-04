import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

function getArg(name: string, fallback: string): string {
  const prefix = `--${name}=`;
  const hit = process.argv.find((arg) => arg.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : fallback;
}

function run(command: string): string {
  try {
    return execSync(command, { stdio: ["ignore", "pipe", "pipe"] }).toString("utf8").trim();
  } catch {
    return "";
  }
}

function ensureDir(dirPath: string): void {
  fs.mkdirSync(dirPath, { recursive: true });
}

function toIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function getIsoWeekLabel(date: Date): string {
  const utcDate = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = utcDate.getUTCDay() || 7;
  utcDate.setUTCDate(utcDate.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((utcDate.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${utcDate.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function main(): void {
  const since = getArg("since", "7.days");
  const until = getArg("until", "now");

  const commitsRaw = run(`git log --since="${since}" --until="${until}" --pretty=format:%H`);
  const authorsRaw = run(`git log --since="${since}" --until="${until}" --pretty=format:%ae`);
  const mergeRaw = run(`git log --since="${since}" --until="${until}" --pretty=format:%s`);

  const commitCount = commitsRaw ? commitsRaw.split("\n").filter(Boolean).length : 0;
  const activeContributors = authorsRaw ? new Set(authorsRaw.split("\n").filter(Boolean)).size : 0;
  const mergeCount = mergeRaw
    ? mergeRaw
        .split("\n")
        .filter((line) => line.toLowerCase().includes("merge"))
        .length
    : 0;

  const today = new Date();
  const weekLabel = getIsoWeekLabel(today);

  const report = `# Weekly Loop Status Report

- Generated at: ${new Date().toISOString()}
- Git range: since "${since}" until "${until}"
- KPI schema: docs/loop-kpi.schema.json

## Delivery Velocity
- Commits: ${commitCount}
- Active contributors: ${activeContributors}
- Merge-like commits: ${mergeCount}

## Quality Gates Snapshot
- Lint: run \`npm run lint\`
- Test: run \`npm run test\`
- Coverage: run \`npm run coverage\`
- Contract checks: run \`npm run contract:check\`

## Reliability Snapshot
- Post-deploy smoke: run \`npm run smoke -- --url=https://<service-url>\`
- Rollback guide: docs/deploy-runbook.md

## KPI JSON Template (${weekLabel})
\`\`\`json
{
  "week": "${weekLabel}",
  "generatedAt": "${new Date().toISOString()}",
  "source": {
    "gitRange": "since=${since},until=${until}",
    "environment": "local"
  },
  "deliveryVelocity": {
    "commits": ${commitCount},
    "activeContributors": ${activeContributors},
    "specToCodeLeadTimeHours": 0
  },
  "quality": {
    "lintPassRate": 0,
    "testPassRate": 0,
    "coveragePercent": 0,
    "contractPassRate": 0
  },
  "deliveryReliability": {
    "smokePassRate": 0,
    "rollbackCount": 0,
    "meanRecoveryMinutes": 0
  },
  "notes": "Fill computed percentages from CI outputs."
}
\`\`\`
`;

  const reportsDir = path.join(process.cwd(), "reports");
  ensureDir(reportsDir);
  const reportPath = path.join(reportsDir, `weekly-status-${toIsoDate(today)}.md`);
  fs.writeFileSync(reportPath, report, "utf8");
  console.log(`Weekly report generated: ${reportPath}`);
}

main();
