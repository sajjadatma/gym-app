export function readableOnColor(hex: string): string {
  const value = hex.replace("#", "")
  const channels = [0, 2, 4].map((offset) =>
    Number.parseInt(value.slice(offset, offset + 2), 16),
  )
  if (channels.some((channel) => Number.isNaN(channel))) return "#ffffff"
  const [red, green, blue] = channels.map((channel) => {
    const normalized = channel / 255
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4
  })
  const luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
  return luminance > 0.179 ? "#171b18" : "#ffffff"
}
