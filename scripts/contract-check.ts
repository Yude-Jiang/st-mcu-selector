import fs from "node:fs";
import path from "node:path";

type JsonObject = Record<string, unknown>;

function readJson(filePath: string): JsonObject {
  return JSON.parse(fs.readFileSync(filePath, "utf8")) as JsonObject;
}

function assert(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function checkNoFirebaseLeftover(root: string): void {
  assert(
    !fs.existsSync(path.join(root, "firebase-blueprint.json")),
    "firebase-blueprint.json is template leftover and must stay deleted",
  );
}

function checkMetadataContract(root: string): void {
  const metadata = readJson(path.join(root, "metadata.json"));
  const name = String(metadata.name || "");
  const description = String(metadata.description || "");
  const capabilities = metadata.majorCapabilities;

  assert(name.toLowerCase().includes("mcu"), "metadata.name must describe MCU Selector");
  assert(description.length > 20, "metadata.description must be a descriptive string (length > 20)");
  assert(/stm32|mcu/i.test(description), "metadata.description must mention MCU or STM32");
  assert(Array.isArray(capabilities) && capabilities.length > 0, "metadata.majorCapabilities must be a non-empty array");
  const blob = JSON.stringify(metadata).toLowerCase();
  assert(!blob.includes("macroinsight"), "metadata must not carry MacroInsight template leftovers");
  assert(!blob.includes("cloud run static hosting"), "metadata must not claim Cloud Run static hosting");
}

function checkCloudRunContract(root: string): void {
  const docker = fs.readFileSync(path.join(root, "Dockerfile"), "utf8");
  assert(/EXPOSE 8080/.test(docker), "Dockerfile must EXPOSE 8080");
  for (const relative of ["server/routes/parse.py", "server/routes/selection.py", "server/engine/nl_must.py"]) {
    assert(fs.existsSync(path.join(root, relative)), `${relative} must exist`);
  }
}

function main(): void {
  const root = process.cwd();
  checkNoFirebaseLeftover(root);
  checkMetadataContract(root);
  checkCloudRunContract(root);
  console.log("Contract checks passed: MCU metadata + Dockerfile 8080; no firebase blueprint");
}

main();
