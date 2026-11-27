export const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024;

const ALLOWED_MEDIA_PREFIXES = ["video/", "audio/", "image/"] as const;
const MEDIA_EXTENSIONS = new Set([
  "mp4", "m4v", "mov", "mkv", "webm", "avi", "mpeg", "mpg", "3gp",
  "mp3", "wav", "m4a", "aac", "flac", "ogg", "opus", "wma",
  "jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "avif",
]);

export interface MediaFileLike {
  name: string;
  type: string;
  size: number;
}

export interface MediaValidationResult {
  accepted: MediaFileLike[];
  rejected: Array<{ file: MediaFileLike; reason: "unsupported" | "too_large" }>;
}

export function validateMediaFiles(files: readonly MediaFileLike[]): MediaValidationResult {
  const accepted: MediaFileLike[] = [];
  const rejected: MediaValidationResult["rejected"] = [];

  for (const file of files) {
    if (!Number.isFinite(file.size) || file.size < 0 || file.size > MAX_UPLOAD_BYTES) {
      rejected.push({ file, reason: "too_large" });
      continue;
    }
    const mime = file.type.toLowerCase();
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    const supported = ALLOWED_MEDIA_PREFIXES.some((prefix) => mime.startsWith(prefix)) || MEDIA_EXTENSIONS.has(extension);
    if (!supported) rejected.push({ file, reason: "unsupported" });
    else accepted.push(file);
  }

  return { accepted, rejected };
}
