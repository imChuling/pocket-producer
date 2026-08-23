# Draft issue for github.com/audiotool/nexus (post after user approval)

Title: insertSample crashes in any minified production build: "Cannot read
properties of undefined (reading 'slice')"

---

## Summary

`transaction.insertSample()` (and, we believe, any entity creation that
applies overwrites containing nested messages) throws
`TypeError: Cannot read properties of undefined (reading 'slice')` in
production builds bundled with a minifier, while working fine in dev
builds and in Node. Nexus SDK 0.0.17.

## Root cause

In `dist/synced-document-*.js` the overwrite applier decides whether a
field value is an entity pointer by comparing protobuf message classes
**by constructor name**:

```js
// Un() in dist/synced-document-ywEybIAl.js:4302
if (t.T.name === q.name) {
  return new q({
    fieldIndex: a.fieldIndex.slice(),   // <- crashes
    entityId: a.entityId
  });
}
```

Under minification every message class is emitted as `class e { ... }`
(the inner self-reference name), so `SomeMessage.name === "e"` for all
~300 generated classes. The check then matches **every** message-typed
field, plain nested-message overwrites (e.g. the `region` params of
`insertSample`) are treated as pointers, and `fieldIndex` is undefined.

This is why the crash only appears in minified bundles: unminified
builds keep distinct class names and only real `Pointer` fields match.

Reproduction: any app bundled with Next.js/Turbopack (or any bundler
that minifies class names) calling `document.modify(t =>
t.insertSample(...))` against any document. Dev server works; `next
build` output crashes.

## Fix (one line)

Compare the protobuf `typeName` (a string literal, immune to
minification) instead of the constructor name:

```js
if (t.T.typeName === q.typeName) {
```

`q.typeName` is `"audiotool.document.v1.Pointer"`, set via the generated
`o(d, "typeName", "audiotool.document.v1.Pointer")`.

We ship this as a pnpm patch in our hackathon project and have verified
the full insert/undo flow works in production with it:
https://github.com/imChuling/pocket-producer/blob/main/frontend/patches/@audiotool__nexus.patch

## Secondary observation

When a `modify()` transaction callback throws, a subsequent `modify()`
call never starts (its callback is never invoked) — the internal
transaction lock appears not to be released on exception. With the
primary bug fixed this path is harder to hit, but it turns any
in-transaction exception into a permanent hang for the session.

Happy to open a PR against the SDK source if useful.
