const { request } = require("./request");

function recommend(body) {
  return request({ url: "/api/recommend", method: "POST", data: body });
}

function compare(body) {
  return request({ url: "/api/compare", method: "POST", data: body });
}

function inspect(partNumber) {
  const query = encodeURIComponent(String(partNumber || ""));
  return request({ url: `/api/inspect?part_number=${query}`, method: "GET" });
}

function health() {
  return request({ url: "/api/health", method: "GET" });
}

function parseRequirements(text) {
  return request({ url: "/api/parse-requirements", method: "POST", data: { text } });
}

module.exports = { recommend, compare, inspect, health, parseRequirements };
