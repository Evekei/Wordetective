import { loadPyodide } from "./pyodide/pyodide.mjs";

async function initialize() {
  const runtime = await loadPyodide({ indexURL: new URL("./pyodide/", import.meta.url).href });
  const manifest = await fetch(new URL("./manifest.json", import.meta.url));
  if (!manifest.ok) throw new Error("规则引擎清单加载失败");
  await Promise.all([
    runtime.loadPackage(["pydantic", "sqlalchemy", "pyyaml", "pandas"]),
    manifest.json().then((paths) => Promise.all(paths.map(async (path) => {
      const response = await fetch(new URL(path, import.meta.url));
      if (!response.ok) throw new Error("规则引擎资源加载失败");
      const destination = "/engine/" + path;
      runtime.FS.mkdirTree(destination.slice(0, destination.lastIndexOf("/")));
      runtime.FS.writeFile(destination, new Uint8Array(await response.arrayBuffer()));
    }))),
  ]);
  runtime.runPython(`
import json, sys
sys.path.insert(0, "/engine")
from app.detection.compliance_rules import _load_rule_store_from_db
from app.detection.engine import detect_text
from app.schemas.detection import DetectRequest
_load_rule_store_from_db()

def detect(payload):
    return detect_text(None, DetectRequest.model_validate_json(payload)).model_dump_json()
`);
  return runtime.globals.get("detect");
}

let engine;
self.onmessage = async ({ data }) => {
  try {
    engine ??= initialize();
    const detect = await engine;
    self.postMessage({ result: JSON.parse(detect(JSON.stringify(data))) });
  } catch (error) {
    console.error(error);
    self.postMessage({ error: "规则审查失败，请重试。" });
  }
};

