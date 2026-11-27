export type VisualProfile = {
  brightness: number;
  contrast: number;
  tone: "warm" | "cool" | "balanced";
  colorfulness: number;
};

/** Samples a locally fetched preview image in-browser. No image pixels are uploaded. */
export function analyzePreviewPixels(image: HTMLImageElement): VisualProfile | null {
  if (!image.naturalWidth || !image.naturalHeight) return null;
  const canvas = document.createElement("canvas");
  const width = 48;
  const height = Math.max(1, Math.round((image.naturalHeight / image.naturalWidth) * width));
  canvas.width = width;
  canvas.height = Math.min(48, height);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  try {
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let brightness = 0;
    let red = 0;
    let green = 0;
    let blue = 0;
    let saturation = 0;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4) {
      const r = pixels[i] / 255;
      const g = pixels[i + 1] / 255;
      const b = pixels[i + 2] / 255;
      brightness += 0.2126 * r + 0.7152 * g + 0.0722 * b;
      red += r; green += g; blue += b;
      saturation += Math.max(r, g, b) - Math.min(r, g, b);
      count += 1;
    }
    if (!count) return null;
    const mean = brightness / count;
    let variance = 0;
    for (let i = 0; i < pixels.length; i += 4) {
      const luminance = 0.2126 * (pixels[i] / 255) + 0.7152 * (pixels[i + 1] / 255) + 0.0722 * (pixels[i + 2] / 255);
      variance += (luminance - mean) ** 2;
    }
    const r = red / count;
    const b = blue / count;
    return {
      brightness: Math.round(mean * 100),
      contrast: Math.round(Math.sqrt(variance / count) * 100),
      tone: r - b > 0.045 ? "warm" : b - r > 0.045 ? "cool" : "balanced",
      colorfulness: Math.round((saturation / count) * 100),
    };
  } catch {
    return null;
  }
}
