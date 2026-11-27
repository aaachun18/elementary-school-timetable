// WCAG 2 contrast between two colors, for checking the design tokens
// (styles/tokens.test.ts). Pure, no DOM.

// WCAG AA for normal-size text.
export const MIN_TEXT_CONTRAST = 4.5;

function channelToLinear(channel: number): number {
  const value = channel / 255;
  return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
}

// "#00749b" or "#fff" -> relative luminance (0 = black, 1 = white).
export function relativeLuminance(hex: string): number {
  const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (match === null) {
    throw new Error(`不是十六進位色碼：${hex}`);
  }
  const digits =
    match[1].length === 3
      ? match[1]
          .split("")
          .map((digit) => digit + digit)
          .join("")
      : match[1];
  const [red, green, blue] = [0, 2, 4].map((start) => channelToLinear(parseInt(digits.slice(start, start + 2), 16)));
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

// `foreground` at `alpha` (0-1) painted over `background`, as one "#rrggbb"
// -- what a semi-transparent color (text-white/85, a white 6% grid line)
// actually shows, so its contrast can be checked too.
export function blendOver(foreground: string, alpha: number, background: string): string {
  const channels = (hex: string): number[] => {
    relativeLuminance(hex); // validates the format
    const digits = hex.trim().slice(1);
    const full = digits.length === 3 ? digits.split("").map((digit) => digit + digit).join("") : digits;
    return [0, 2, 4].map((start) => parseInt(full.slice(start, start + 2), 16));
  };
  const top = channels(foreground);
  const bottom = channels(background);
  return `#${top
    .map((channel, index) => Math.round(alpha * channel + (1 - alpha) * bottom[index]))
    .map((channel) => channel.toString(16).padStart(2, "0"))
    .join("")}`;
}

export function contrastRatio(foreground: string, background: string): number {
  const first = relativeLuminance(foreground);
  const second = relativeLuminance(background);
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return (lighter + 0.05) / (darker + 0.05);
}

// Every `--color-<name>: #hex;` inside a CSS @theme block -> { name: hex }.
export function parseThemeColors(css: string): Map<string, string> {
  const theme = /@theme\s*\{([\s\S]*?)\n\}/.exec(css);
  if (theme === null) {
    throw new Error("找不到 @theme 區塊");
  }
  const colors = new Map<string, string>();
  for (const match of theme[1].matchAll(/--color-([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;/g)) {
    colors.set(match[1], match[2].toLowerCase());
  }
  return colors;
}
