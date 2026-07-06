import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAdminExportQuery,
  handleAdminCreateUserSubmit,
  renderQuestionLineage,
  retireQuestion,
  restoreQuestion
} from "./dashboard.js";

test("admin create user keeps form reference across async create", async () => {
  let prevented = false;
  const form = {
    fields: {
      username: "new.student",
      display_name: "New Student",
      password: "temporary1",
      role: "student"
    },
    resetCount: 0,
    reset() {
      this.resetCount += 1;
    }
  };
  let currentTarget = form;

  const apiCalls = [];
  const statuses = [];
  let reloadCount = 0;

  await handleAdminCreateUserSubmit(
    {
      preventDefault() {
        prevented = true;
      },
      get currentTarget() {
        return currentTarget;
      }
    },
    {
      apiPostFn: async (path, payload) => {
        apiCalls.push({ path, payload });
        currentTarget = null;
        return { id: 42 };
      },
      formDataFactory: (form) => ({
        get(name) {
          return form.fields[name];
        }
      }),
      renderUsers: async () => {
        reloadCount += 1;
      },
      showStatus: (message) => {
        statuses.push(message);
      }
    }
  );

  assert.equal(prevented, true);
  assert.equal(form.resetCount, 1);
  assert.deepEqual(apiCalls, [{
    path: "/api/users",
    payload: {
      username: "new.student",
      display_name: "New Student",
      password: "temporary1",
      role: "student"
    }
  }]);
  assert.equal(reloadCount, 1);
  assert.deepEqual(statuses, ["User created."]);
});

test("admin create user shows backend error without resetting or reloading", async () => {
  const form = {
    fields: {
      username: "existing",
      display_name: "Existing User",
      password: "temporary1",
      role: "student"
    },
    resetCount: 0,
    reset() {
      this.resetCount += 1;
    }
  };
  const statuses = [];
  let reloadCount = 0;

  await handleAdminCreateUserSubmit(
    {
      preventDefault() {},
      currentTarget: form
    },
    {
      apiPostFn: async () => {
        throw new Error("Username already exists");
      },
      formDataFactory: (targetForm) => ({
        get(name) {
          return targetForm.fields[name];
        }
      }),
      renderUsers: async () => {
        reloadCount += 1;
      },
      showStatus: (message) => {
        statuses.push(message);
      }
    }
  );

  assert.equal(form.resetCount, 0);
  assert.equal(reloadCount, 0);
  assert.deepEqual(statuses, ["User create failed: Username already exists"]);
});

test("admin export options build expected query params", () => {
  const formData = new FormData();
  formData.set("include_lineage", "on");
  formData.set("include_review_metadata", "on");
  formData.set("include_retired", "on");

  assert.equal(
    buildAdminExportQuery("SY0-701", formData),
    "/api/export/SY0-701?include_lineage=true&include_review_metadata=true&include_retired=true"
  );
});

test("retire and restore question helpers call correct APIs", async () => {
  const calls = [];
  const apiPostFn = async (path, payload) => {
    calls.push({ path, payload });
    return { status: "ok" };
  };

  await retireQuestion("q-7", apiPostFn);
  await restoreQuestion("q-7", apiPostFn);

  assert.deepEqual(calls, [
    { path: "/api/questions/q-7/retire", payload: {} },
    { path: "/api/questions/q-7/restore", payload: {} }
  ]);
});

test("question lineage viewer renders source metadata and evidence", () => {
  const html = renderQuestionLineage([
    {
      source_title: "Security+ Official Notes",
      source_type: "official_course_material",
      source_confidence: "verified",
      source_verification_status: "verified",
      evidence_text: "TLS encrypts traffic.",
      lineage_reason: "source_chunk"
    }
  ]);

  assert.match(html, /Security\+ Official Notes/);
  assert.match(html, /official_course_material/);
  assert.match(html, /TLS encrypts traffic/);
  assert.match(html, /source_chunk/);
});
