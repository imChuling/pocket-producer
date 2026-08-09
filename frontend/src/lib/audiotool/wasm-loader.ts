// Browser WASM loader for the Nexus document validator.
//
// The SDK's built-in loader refuses to run whenever `typeof process !==
// "undefined"`, which it treats as "server-side". Next.js polyfills `process`
// in the browser bundle, so that check misfires and `client.open()` throws
// "server-side usage requires createDiskWasmLoader()". `createBrowserWasmLoader`
// is not exported, so we implement the (tiny) public `WasmLoader` interface
// ourselves and hand it to `createAudiotoolClient`.
//
// Assets come from the same CDN the SDK's own browser loader uses. The
// uncompressed validator is ~37 MB in the package; the CDN serves a ~6 MB
// gzipped build with `Content-Type: application/wasm`, so it can be compiled
// as a stream.

import type { WasmLoader } from "@audiotool/nexus";

const CDN_BASE =
  "https://cdn.audiotool.com/website-assets/document-service/a81fea1396cecac7a7c590baed83aaf1a1265246";

export function createBrowserWasmLoader(base: string = CDN_BASE): WasmLoader {
  return {
    async executeRuntime() {
      // Go's wasm_exec.js is a classic script that assigns `Go` to globalThis;
      // the bundler must not try to resolve this URL at build time.
      await import(/* webpackIgnore: true */ /* @vite-ignore */ `${base}/wasm_exec.js`);
    },
    async loadModule() {
      const response = await fetch(`${base}/document_validator.wasm.gz`);
      if (!response.ok) {
        throw new Error(
          `Could not fetch the Audiotool document validator (${response.status})`,
        );
      }
      return WebAssembly.compileStreaming(response);
    },
  };
}
