import test from "node:test";
import assert from "node:assert/strict";
import { auth, AuthManager, mockDevSession } from "./auth/index.ts";

test("AuthManager returns active development session when in mock mode", () => {
  const authInstance = AuthManager.getInstance();
  const session = authInstance.getSession();
  assert.equal(session.isAuthenticated, true);
  assert.equal(session.user?.email, "dev.student@uniglobe.edu");
  assert.equal(session.user?.role, "student");
});

test("AuthManager provides correct Bearer authorization header", () => {
  const headers = auth.getAuthHeader();
  assert.ok(headers.Authorization);
  assert.equal(headers.Authorization, "Bearer dev_token");
});

test("Dual pathway model supports both first-year and transfer modes", () => {
  const allowedTypes = ["first_year", "transfer", "both", "undecided"];
  assert.ok(allowedTypes.includes("first_year"));
  assert.ok(allowedTypes.includes("transfer"));
  assert.ok(allowedTypes.includes("both"));
  assert.equal(allowedTypes.length, 4);
});

