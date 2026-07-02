import assert from "node:assert/strict";
import test from "node:test";

import { buildSourceUploadFormData, uploadSourceMaterial } from "./sourceLibrary.js";

test("source upload form data includes library metadata and file", () => {
  const file = new File(["Security+ notes"], "security-notes.md", { type: "text/markdown" });

  const formData = buildSourceUploadFormData({
    libraryId: 7,
    title: "Security+ Notes",
    sourceType: "markdown",
    authorityLevel: 5,
    confidence: "reviewed",
    verificationStatus: "needs_review",
    copyrightStatus: "owned",
    originalUrl: "https://example.test/source"
  }, file);

  assert.equal(formData.get("library_id"), "7");
  assert.equal(formData.get("title"), "Security+ Notes");
  assert.equal(formData.get("source_type"), "markdown");
  assert.equal(formData.get("authority_level"), "5");
  assert.equal(formData.get("confidence"), "reviewed");
  assert.equal(formData.get("verification_status"), "needs_review");
  assert.equal(formData.get("copyright_status"), "owned");
  assert.equal(formData.get("original_url"), "https://example.test/source");
  assert.equal(formData.get("file").name, "security-notes.md");
});

test("source upload keeps backend duplicate message", async () => {
  const file = new File(["duplicate"], "notes.txt", { type: "text/plain" });

  await assert.rejects(
    () => uploadSourceMaterial(
      {
        libraryId: 7,
        title: "Notes",
        sourceType: "txt",
        authorityLevel: 3,
        confidence: "unverified",
        verificationStatus: "not_reviewed",
        copyrightStatus: "unknown",
        originalUrl: ""
      },
      file,
      async () => {
        throw new Error("Duplicate source upload detected. Existing source material: Notes");
      }
    ),
    /Duplicate source upload detected/
  );
});
