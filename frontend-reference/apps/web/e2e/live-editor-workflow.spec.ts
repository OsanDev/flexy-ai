import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("live browser workflow: register, upload media, edit timeline and download real MP4", async ({ page }) => {
  test.setTimeout(120_000);
  const email = `live-e2e-${Date.now()}@example.test`;
  const password = "flexy-live-e2e-password-2026";
  const source = join(tmpdir(), `flexy-live-source-${Date.now()}.mp4`);
  let uploadedMediaId = "";

  execFileSync("ffmpeg", [
    "-hide_banner", "-loglevel", "error", "-y",
    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", source,
  ], { stdio: "pipe", timeout: 30_000 });

  try {
    page.on("response", async (response) => {
      if (response.request().method() === "POST" && new URL(response.url()).pathname.endsWith("/media")) {
        const payload = await response.json().catch(() => null) as { id?: string } | null;
        if (payload?.id) uploadedMediaId = payload.id;
      }
    });

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Sign in to continue" })).toBeVisible();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /create account/i }).click();
    await expect(page.getByText(email)).toBeVisible();

    await page.getByLabel("New project name").fill("Live MP4 verification");
    await page.getByRole("button", { name: /create project/i }).click();
    await expect(page.getByText("Project workspace")).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles(source);
    await expect(page.getByText("Imported 1 of 1 files.")).toBeVisible({ timeout: 30_000 });
    await page.getByLabel("Video / image asset").selectOption({ index: 1 });
    await page.getByRole("button", { name: "Add video clip +" }).click();
    await expect(page.locator(".track-clip.video")).toHaveCount(1);
    await expect(page.getByText("All changes saved")).toBeVisible({ timeout: 20_000 });

    await expect.poll(() => uploadedMediaId).not.toBe("");
    await page.getByRole("button", { name: "Advanced JSON" }).click();
    await page.getByLabel("Render graph (JSON)").fill(JSON.stringify({
      clips: [{ media_id: uploadedMediaId, source_start: 0, duration: 1, timeline_start: 0 }],
      audio_clips: [], captions: [], width: 640, height: 360, frame_rate: 24, video_bitrate: "2M",
    }));
    await expect(page.getByRole("button", { name: "Start export" })).toBeEnabled({ timeout: 20_000 });
    await page.getByRole("button", { name: "Start export" }).click();
    await expect(page.getByRole("button", { name: "Download MP4" })).toBeVisible({ timeout: 60_000 });

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download MP4" }).click();
    const download = await downloadPromise;
    const path = await download.path();
    expect(path).toBeTruthy();
    const bytes = readFileSync(path!);
    expect(bytes.byteLength).toBeGreaterThan(1_000);
    expect(bytes.toString("ascii", 4, 8)).toBe("ftyp");
  } finally {
    // The runner is ephemeral; remove the generated fixture after the browser flow.
    try { unlinkSync(source); } catch {}
  }
});
