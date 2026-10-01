const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const apiSource = fs.readFileSync(
  path.join(__dirname, "..", "js", "api.js"),
  "utf8",
);

function resolveWith({ origin, apiBase }) {
  const context = {
    window: {
      location: { origin },
      CLIMATEINSIGHT_CONFIG: apiBase === undefined ? {} : { apiBase },
    },
    document: { dispatchEvent() {} },
    CustomEvent: class CustomEvent {},
    fetch() {},
    console,
  };
  vm.runInNewContext(`${apiSource}\nglobalThis.result = API_BASE;`, context);
  return context.result;
}

assert.equal(
  resolveWith({ origin: "https://climate.example" }),
  "https://climate.example/api",
);
assert.equal(
  resolveWith({ origin: "http://localhost:3000", apiBase: "http://localhost:5000/api" }),
  "http://localhost:5000/api",
);
assert.equal(
  resolveWith({ origin: "https://frontend.example", apiBase: "https://backend.example/" }),
  "https://backend.example/api",
);
assert.equal(
  resolveWith({ origin: "https://frontend.example", apiBase: "  https://backend.example/api/  " }),
  "https://backend.example/api",
);

console.log("API base configuration tests passed");
