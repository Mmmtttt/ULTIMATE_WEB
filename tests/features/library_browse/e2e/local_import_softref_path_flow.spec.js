const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const {
  test,
  expect,
  startApiRequestRecorder,
  hasApiCall,
} = require("../../../shared/e2e_helpers");

const PNG_1X1_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgN6QHdwAAAAASUVORK5CYII=";

const REPO_ROOT = path.resolve(__dirname, "../../../../../");
const E2E_RUNTIME_ROOT = path.join(REPO_ROOT, "tests", ".runtime", "e2e");
const E2E_SOURCES_ROOT = path.join(E2E_RUNTIME_ROOT, "sources", "softref-e2e");

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writePng(filePath) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, Buffer.from(PNG_1X1_BASE64, "base64"));
}

function runPython(script, args = []) {
  const candidates = process.platform === "win32" ? ["python", "python3", "py"] : ["python3", "python"];
  const errors = [];
  for (const command of candidates) {
    const result = spawnSync(command, ["-c", script, ...args], {
      cwd: REPO_ROOT,
      encoding: "utf-8",
    });
    if (result.status === 0) return;
    errors.push(`${command}: status=${result.status}, stderr=${result.stderr || ""}`);
  }
  throw new Error(`python script failed: ${errors.join("\n")}`);
}

function hasPy7zr() {
  const checkScript =
    "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('py7zr') else 1)";
  const candidates = process.platform === "win32" ? ["python", "python3", "py"] : ["python3", "python"];
  for (const command of candidates) {
    const result = spawnSync(command, ["-c", checkScript], {
      cwd: REPO_ROOT,
      encoding: "utf-8",
    });
    if (result.status === 0) return true;
  }
  return false;
}

function parseJsonSafe(payload) {
  if (!payload || typeof payload !== "string") return null;
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

function createZipWithPng(zipPath, memberPath) {
  const script = `
import base64, pathlib, zipfile, sys
zip_path = pathlib.Path(sys.argv[1])
member_path = sys.argv[2]
png_b64 = sys.argv[3]
zip_path.parent.mkdir(parents=True, exist_ok=True)
data = base64.b64decode(png_b64.encode("ascii"))
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(member_path, data)
`;
  runPython(script, [zipPath, memberPath, PNG_1X1_BASE64]);
}

function createEncrypted7zWithPng(archivePath, memberPath, password) {
  const script = `
import base64, pathlib, sys
import py7zr
archive_path = pathlib.Path(sys.argv[1])
member_path = sys.argv[2]
password = sys.argv[3]
png_b64 = sys.argv[4]
archive_path.parent.mkdir(parents=True, exist_ok=True)
data = base64.b64decode(png_b64.encode("ascii"))
with py7zr.SevenZipFile(str(archive_path), "w", password=password) as archive:
    archive.writestr(data, member_path)
`;
  runPython(script, [archivePath, memberPath, password, PNG_1X1_BASE64]);
}

function ensureSwitchState(page, expectedOn) {
  return page.locator(".import-mode-switch .van-switch").first().evaluate((node, on) => {
    const isOn = node.classList.contains("van-switch--on");
    if (isOn !== on) {
      node.click();
    }
  }, expectedOn);
}

async function clearSessionById(request, sessionId) {
  const id = String(sessionId || "").trim();
  if (!id || id === "-") return;
  await request.delete(`/api/v1/comic/batch-upload/session/${encodeURIComponent(id)}`);
}

async function parseSoftRefPath(page, sourcePath, { archivePassword = "" } = {}) {
  const apiRequests = startApiRequestRecorder(page);

  await page.goto("/comic-local-import");
  await expect(page).toHaveURL(/\/comic-local-import$/);

  await ensureSwitchState(page, true);

  const sourceInput = page.locator(".source-panel .van-field__control").first();
  await sourceInput.fill(sourcePath);

  if (archivePassword) {
    const passwordInput = page.locator(".source-panel .van-field__control").nth(1);
    await passwordInput.fill(archivePassword);
  }

  await page.locator(".source-panel .van-button--block").first().click();

  await expect
    .poll(
      () =>
        hasApiCall(
          apiRequests,
          (item) => {
            if (item.method !== "POST") return false;
            if (!item.url.includes("/api/v1/comic/batch-upload/session/from-path")) return false;
            const body = parseJsonSafe(item.body);
            if (!body) return false;
            if (body.import_mode !== "softlink_ref") return false;
            if (body.source_path !== sourcePath) return false;
            if (archivePassword && body.archive_password !== archivePassword) return false;
            return true;
          },
        ),
      { timeout: 10000 },
    )
    .toBeTruthy();

  await expect
    .poll(async () => {
      const text = (await page.locator(".session-card .value.mono").first().textContent()) || "";
      return text.trim();
    })
    .not.toBe("-");

  const sid = ((await page.locator(".session-card .value.mono").first().textContent()) || "").trim();
  return { apiRequests, sessionId: sid };
}

test.beforeAll(() => {
  ensureDir(E2E_SOURCES_ROOT);
});

test("softref path parse sends softlink_ref and renders directory tree", async ({ page, request }) => {
  const stamp = Date.now();
  const author = `E2EAuthor${stamp}`;
  const title = `E2ESoftRefDir${stamp}`;
  const sourceDir = path.join(E2E_SOURCES_ROOT, `dir-${stamp}`);
  let sessionId = "";

  try {
    writePng(path.join(sourceDir, author, title, "001.png"));
    const parsed = await parseSoftRefPath(page, sourceDir);
    sessionId = parsed.sessionId;

    await expect(page.locator(".tree-row .tree-name").filter({ hasText: title }).first()).toBeVisible();
  } finally {
    await clearSessionById(request, sessionId);
    fs.rmSync(sourceDir, { recursive: true, force: true });
  }
});

test("softref path parse supports zip source in tree stage", async ({ page, request }) => {
  const stamp = Date.now();
  const author = `E2EAuthorZip${stamp}`;
  const title = `E2ESoftRefZip${stamp}`;
  const sourceDir = path.join(E2E_SOURCES_ROOT, `zip-${stamp}`);
  const zipPath = path.join(sourceDir, author, `${title}.zip`);
  let sessionId = "";

  try {
    createZipWithPng(zipPath, `${title}/001.png`);
    const parsed = await parseSoftRefPath(page, sourceDir);
    sessionId = parsed.sessionId;

    await expect(page.locator(".tree-row .tree-name").filter({ hasText: title }).first()).toBeVisible();
  } finally {
    await clearSessionById(request, sessionId);
    fs.rmSync(sourceDir, { recursive: true, force: true });
  }
});

test("softref path parse sends archive password for encrypted 7z", async ({ page, request }) => {
  test.skip(!hasPy7zr(), "py7zr is not available in current runner");

  const stamp = Date.now();
  const author = `E2EAuthorEnc${stamp}`;
  const title = `E2ESoftRefEnc${stamp}`;
  const password = `e2e-pass-${stamp}`;
  const sourceDir = path.join(E2E_SOURCES_ROOT, `enc-${stamp}`);
  const archivePath = path.join(sourceDir, author, `${title}.7z`);
  let sessionId = "";

  try {
    createEncrypted7zWithPng(archivePath, `${title}/001.png`, password);
    const parsed = await parseSoftRefPath(page, sourceDir, { archivePassword: password });
    sessionId = parsed.sessionId;

    await expect(page.locator(".tree-row .tree-name").filter({ hasText: title }).first()).toBeVisible();
  } finally {
    await clearSessionById(request, sessionId);
    fs.rmSync(sourceDir, { recursive: true, force: true });
  }
});
