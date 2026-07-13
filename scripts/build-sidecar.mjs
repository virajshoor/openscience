import { mkdir, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import { join } from "node:path";

if (process.platform !== "darwin" || process.arch !== "arm64") {
  throw new Error("OpenScience releases currently support macOS on Apple Silicon only.");
}
const target = "aarch64-apple-darwin";

const binaries = join("src-tauri", "binaries");
const workpath = join("src-tauri", ".sidecar-build");
await mkdir(binaries, { recursive: true });
await rm(workpath, { recursive: true, force: true });

const args = [
  "run", "--with", "pyinstaller", "pyinstaller",
  "--noconfirm", "--clean", "--onefile",
  "--name", `openscience-sidecar-${target}`,
  "--hidden-import", "sidecar.tools.uniprot",
  "--hidden-import", "sidecar.tools.pdb",
  "--hidden-import", "sidecar.tools.entrez",
  "--hidden-import", "sidecar.tools.chembl",
  "--distpath", "../src-tauri/binaries",
  "--workpath", "../src-tauri/.sidecar-build",
  "--specpath", "../src-tauri/.sidecar-build",
  "frozen_entry.py",
];

await new Promise((resolve, reject) => {
  const child = spawn("uv", args, {
    cwd: "sidecar",
    stdio: "inherit",
    shell: false,
  });
  child.on("error", reject);
  child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`PyInstaller exited with ${code}`)));
});
