/**
 * The only parts of the Sentry SDK the browser uses. Importing these by name (rather than
 * `import("@sentry/nextjs")`, which keeps every export) lets the build leave out the rest, such as
 * session replay and the feedback widget. Loaded on demand by instrumentation-client.ts.
 */
export { captureException, captureRouterTransitionStart, init } from "@sentry/nextjs";
