/**
 * The public read-only demo account (/demo). Off unless
 * NEXT_PUBLIC_DEMO_ENABLED=1 at build time: the entry links are hidden and
 * /demo returns 404. Set the variable and redeploy to turn it back on.
 */
export const DEMO_ENABLED = process.env.NEXT_PUBLIC_DEMO_ENABLED === "1";
