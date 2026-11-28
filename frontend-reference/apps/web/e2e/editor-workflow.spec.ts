import { expect, test } from "@playwright/test";

test("mocked browser workflow: sign in, import, edit, autosave and download render response", async ({ page }) => {
  const projectId = "browser-project";
  const mediaId = "media-video-1";
  const savedDocuments: Array<Record<string, unknown>> = [];
  let renderStarted = false;
  let renderFinished = false;
  let media: Array<Record<string, unknown>> = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200, extraHeaders: Record<string, string> = {}) => route.fulfill({
      status, contentType: "application/json", headers: extraHeaders, body: JSON.stringify(body),
    });

    if (path === "/api/auth/me" && method === "GET") return json({ detail: "Not signed in" }, 401);
    if (path === "/api/auth/login" && method === "POST") {
      return json({ id: "user-1", email: "editor@example.com" }, 200, {
        "set-cookie": "flexy_csrf=e2e-csrf-token; Path=/; SameSite=Lax",
      });
    }
    if (path === "/api/projects" && method === "GET") return json({ projects: [], folders: [], sort: "updated_desc" });
    if (path === `/api/projects/${projectId}` && method === "GET") {
      return json({
        id: projectId, name: "Browser Test Project", revision: 1, updated_at: new Date().toISOString(),
        project: { timeline_document: { videoClips: [], audioClips: [], captions: [], width: 1920, height: 1080, frameRate: 30, exportPreset: "1080p", videoBitrate: "12M", ducking: false } },
      });
    }
    if (path === `/api/projects/${projectId}/media` && method === "GET") return json({ media });
    if (path === `/api/projects/${projectId}/media` && method === "POST") {
      media = [{ id: mediaId, project_id: projectId, filename: "sample.mp4", mime_type: "video/mp4", size_bytes: 128, duration: 5 }];
      return json(media[0]);
    }
    if (path.endsWith(`/media/${mediaId}/thumbnail`)) return route.fulfill({ status: 404, body: "" });
    if (path.endsWith(`/media/${mediaId}/waveform`)) return json({ media_id: mediaId, points: [0.1, 0.4, 0.8] });
    if (path === "/api/projects" && method === "POST") {
      const body = request.postDataJSON() as { project?: { timeline_document?: Record<string, unknown> } };
      if (body.project?.timeline_document) savedDocuments.push(body.project.timeline_document);
      return json({ id: projectId, name: "Browser Test Project", revision: savedDocuments.length + 1, updated_at: new Date().toISOString() });
    }
    if (path === `/api/projects/${projectId}/render-preflight` && method === "POST") {
      return json({ ready: true, message: "Preflight passed", resolution: "1920x1080", frame_rate: 30, video_duration: 5, warnings: [] });
    }
    if (path === `/api/projects/${projectId}/renders` && method === "GET") {
      return json({ renders: renderFinished ? [{ id: "render-1", project_id: projectId, status: "completed", progress: 100 }] : [] });
    }
    if (path === `/api/projects/${projectId}/renders` && method === "POST") {
      renderStarted = true;
      return json({ id: "render-1", status: "queued", status_url: "/api/renders/render-1" });
    }
    if (path === "/api/renders/render-1" && method === "GET") {
      renderFinished = true;
      return json({ id: "render-1", project_id: projectId, status: "completed", progress: 100 });
    }
    if (path === "/api/renders/render-1/download" && method === "GET") {
      return route.fulfill({ status: 200, contentType: "video/mp4", body: Buffer.from("mock-mp4-download") });
    }
    return json({ detail: `Unhandled E2E API request: ${method} ${path}` }, 404);
  });

  await page.goto("/");
  await page.getByLabel("Email").fill("editor@example.com");
  await page.getByLabel("Password").fill("safe-test-password-123");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText("editor@example.com")).toBeVisible();

  await page.getByLabel("Project ID").fill(projectId);
  await expect(page.getByText("Project workspace")).toBeVisible();
  await expect(page.getByText("No media imported yet.")).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "sample.mp4", mimeType: "video/mp4", buffer: Buffer.from("test-video-placeholder"),
  });
  await expect(page.getByText("Imported 1 of 1 files.")).toBeVisible();
  await page.getByLabel("Video / image asset").selectOption(mediaId);
  await page.getByRole("button", { name: "Add video clip +" }).click();
  await expect(page.locator(".track-clip.video")).toHaveCount(1);

  await page.getByRole("button", { name: /undo/i }).click();
  await expect(page.locator(".track-clip.video")).toHaveCount(0);
  await page.getByRole("button", { name: /redo/i }).click();
  await expect(page.locator(".track-clip.video")).toHaveCount(1);
  await expect.poll(() => savedDocuments.some((doc) => Array.isArray(doc.videoClips) && doc.videoClips.length === 1)).toBeTruthy();
  await expect(page.getByText("All changes saved")).toBeVisible();

  await page.getByRole("button", { name: "Start export" }).click();
  await expect.poll(() => renderStarted).toBeTruthy();
  await expect(page.getByRole("button", { name: "Download MP4" })).toBeVisible({ timeout: 10_000 });
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download MP4" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("flexy-export.mp4");
});
