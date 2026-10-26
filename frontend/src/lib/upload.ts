export const MAX_UPLOAD_BYTES = Number(
  import.meta.env.VITE_MAX_UPLOAD_BYTES ??
    (import.meta.env.VERCEL ? 3_500_000 : 10 * 1024 * 1024),
)

export const MAX_IMPORT_BYTES = Number(
  import.meta.env.VITE_MAX_IMPORT_BYTES ??
    (import.meta.env.VERCEL ? 3_500_000 : 5 * 1024 * 1024),
)
