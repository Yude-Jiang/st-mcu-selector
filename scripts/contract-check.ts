import fs from "node:fs";
import path from "node:path";

type JsonObject = Record<string, unknown>;
type FirestoreCollectionSchema = {
  schema?: {
    $ref?: string;
  };
};

function readJson(filePath: string): JsonObject {
  return JSON.parse(fs.readFileSync(filePath, "utf8")) as JsonObject;
}

function assert(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function checkMetadataContract(root: string): void {
  const metadataPath = path.join(root, "metadata.json");
  const metadata = readJson(metadataPath);

  assert(typeof metadata.name === "string" && metadata.name.length > 0, "metadata.name must be a non-empty string");
  assert(
    typeof metadata.description === "string" && metadata.description.length > 20,
    "metadata.description must be a descriptive string (length > 20)",
  );
  assert(Array.isArray(metadata.requestFramePermissions), "metadata.requestFramePermissions must be an array");
  assert(Array.isArray(metadata.majorCapabilities), "metadata.majorCapabilities must be an array");
}

function checkFirebaseBlueprintContract(root: string): void {
  const blueprintPath = path.join(root, "firebase-blueprint.json");
  const blueprint = readJson(blueprintPath);

  const entitiesCandidate = blueprint.entities;
  if (!entitiesCandidate || typeof entitiesCandidate !== "object") {
    throw new Error("firebase-blueprint.entities must exist");
  }
  const entities = entitiesCandidate as JsonObject;

  const firestoreCandidate = blueprint.firestore;
  if (!firestoreCandidate || typeof firestoreCandidate !== "object") {
    throw new Error("firebase-blueprint.firestore must exist");
  }
  const firestore = firestoreCandidate as Record<string, FirestoreCollectionSchema>;

  const entityKeys = new Set(Object.keys(entities));
  assert(entityKeys.size > 0, "firebase-blueprint.entities cannot be empty");

  for (const [collection, value] of Object.entries(firestore)) {
    const schema = value.schema;
    assert(schema && typeof schema === "object", `firestore.${collection}.schema must exist`);
    const ref = schema?.$ref;
    if (typeof ref !== "string") {
      throw new Error(`firestore.${collection}.schema.$ref must be a non-empty string`);
    }
    assert(typeof ref === "string" && ref.length > 0, `firestore.${collection}.schema.$ref must be a non-empty string`);
    assert(entityKeys.has(ref), `firestore.${collection}.schema.$ref "${ref}" must reference an existing entity`);
  }
}

function main(): void {
  const root = process.cwd();
  checkMetadataContract(root);
  checkFirebaseBlueprintContract(root);
  console.log("Contract checks passed: metadata.json + firebase-blueprint.json");
}

main();
