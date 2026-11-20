/** Vercel refuses function request bodies above ~4.5 MB, so uploads through the web app stop below that. */
export const WEB_UPLOAD_LIMIT_MB = 4;
export const WEB_UPLOAD_LIMIT_BYTES = WEB_UPLOAD_LIMIT_MB * 1024 * 1024;
