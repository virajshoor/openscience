import { spawn } from "node:child_process";

const sidecarUrl = "http://127.0.0.1:7100/health";
const uiUrl = "http://127.0.0.1:1420/";
const children = [];

async function reachable(url, validate) {
  try {
    const response = await fetch(url);
    return response.ok && (validate ? await validate(response) : true);
  } catch {
    return false;
  }
}

function start(command, args, options = {}) {
  const child = spawn(command, args, { stdio: "inherit", shell: process.platform === "win32", ...options });
  children.push(child);
  child.on("exit", (code) => {
    if (code && !stopping) process.exitCode = code;
  });
  return child;
}

async function waitFor(url, validate, label) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if (await reachable(url, validate)) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`${label} did not become ready at ${url}`);
}

let stopping = false;
function stop() {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill();
}

process.on("SIGINT", stop);
process.on("SIGTERM", stop);

try {
  if (await reachable(sidecarUrl, async (response) => (await response.json()).ok === true)) {
    console.log("Reusing healthy sidecar on port 7100.");
  } else {
    console.log("Starting sidecar on port 7100...");
    start("uv", ["run", "python", "-m", "sidecar.__main__"], {
      cwd: "sidecar",
      env: { ...process.env, OS_SIDECAR_PORT: "7100", OS_RUNS_DIR: `${process.env.HOME || process.env.USERPROFILE}/.openscience/runs` },
    });
    await waitFor(sidecarUrl, async (response) => (await response.json()).ok === true, "Sidecar");
  }

  if (await reachable(uiUrl)) {
    console.log("Reusing UI on port 1420.");
  } else {
    console.log("Starting UI on port 1420...");
    start("pnpm", ["dev"]);
    await waitFor(uiUrl, null, "UI");
  }

  console.log("\n=== OpenScience is running ===");
  console.log("  UI:       http://localhost:1420");
  console.log("  Sidecar:  http://127.0.0.1:7100");
  console.log("  Press Ctrl+C to stop processes started by this command.\n");

  if (children.length) {
    await Promise.race(children.map((child) => new Promise((resolve) => child.once("exit", resolve))));
  } else {
    await new Promise((resolve) => setInterval(resolve, 2 ** 31 - 1));
  }
} catch (error) {
  stop();
  console.error(`OpenScience dev launch failed: ${error.message}`);
  process.exitCode = 1;
}
