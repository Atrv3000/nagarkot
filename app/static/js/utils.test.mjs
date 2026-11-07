import assert from "node:assert/strict";
import { escapeHtml } from "./utils.js";

// Test null and undefined
assert.equal(escapeHtml(null), "", "null must return empty string");
assert.equal(escapeHtml(undefined), "", "undefined must return empty string");

// Test normal strings and numbers
assert.equal(escapeHtml("hello world"), "hello world");
assert.equal(escapeHtml(123), "123");
assert.equal(escapeHtml(0), "0");

// Test HTML special characters
assert.equal(
  escapeHtml("<img src=x onerror=alert(1)>"),
  "&lt;img src=x onerror=alert(1)&gt;",
  "Must escape < and >"
);

assert.equal(
  escapeHtml(`"quoted" & 'single'`),
  "&quot;quoted&quot; &amp; &#39;single&#39;",
  "Must escape quotes and ampersands"
);

console.log("All utils.js tests passed successfully!");
