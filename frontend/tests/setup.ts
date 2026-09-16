import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// @testing-library/react's auto-cleanup only registers itself when it finds a global
// `afterEach` (e.g. Jest's globals); this project runs vitest without `test.globals: true`,
// so without this, DOM from one test's render() leaks into the next test in the same file.
afterEach(() => {
  cleanup();
});
