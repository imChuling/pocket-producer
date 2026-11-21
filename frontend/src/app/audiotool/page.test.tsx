import { StrictMode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Fragment } from "@/types";
import AudiotoolPage from "./page";

const env = vi.hoisted(() => ({
  project: "A",
  user: { uid: "musician" },
  library: [] as Fragment[],
  rank: vi.fn(),
  parse: vi.fn(),
  events: vi.fn(),
  insert: vi.fn(),
  link: vi.fn(),
  unlink: vi.fn(),
  play: vi.fn(),
  pause: vi.fn(),
  undo: vi.fn(async () => {}),
  fetchList: vi.fn(),
  download: vi.fn(),
}));

const sketch = {
  _id: "f", user_id: "musician", type: "audio", title: "Sketch",
  tags: ["brass"], emotions: [], themes: [], audio_url: "/audio/f",
  upload: { duration_sec: 2 }, created_at: "2026-01-01T00:00:00Z",
} satisfies Fragment & { upload: { duration_sec: number } };

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: env.user, loading: false }) }));
vi.mock("@/lib/firebase", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/hooks/use-audiotool", () => {
  const document = {
    queryEntities: {
      ofTypes: (type: string) => ({
        get: () => {
          if (type === "audioRegion") return [{ fields: { sample: { value: "s" } } }];
          if (type === "sample") return [{ id: "s", fields: { sampleName: { value: "samples/s" } } }];
          return [];
        },
      }),
    },
  };
  const documents = { A: { ...document }, B: { ...document } };
  return { useAudiotool: () => ({
    status: env.project ? "project-open" : "connected",
    openProjectName: env.project || null,
    projects: [],
    document: () => documents[env.project as keyof typeof documents] ?? null,
    samples: () => ({ download: env.download }),
  }) };
});
vi.mock("@/lib/api", () => ({
  apiFetch: async (path: string) => path.includes("model-card")
    ? { models: [{ id: "rules-v1" }, { id: "text-only-v1" }] } : env.fetchList(path),
  apiPost: async (path: string, body: unknown) => {
    if (path === "/ranking/rank") return env.rank(body);
    if (path === "/ranking/intent") return env.parse(body);
    return env.events(body);
  },
  linkAudiotoolInsert: env.link,
  unlinkAudiotoolInsert: env.unlink,
}));
vi.mock("@/lib/audiotool/insert-fragment", () => ({
  undoInsert: env.undo,
  insertFragment: env.insert,
}));

function suggest() {
  return screen.findByRole("button", { name: /suggest 3/i });
}

beforeEach(() => {
  vi.clearAllMocks();
  env.project = "A";
  env.link.mockResolvedValue({});
  env.unlink.mockResolvedValue({});
  env.insert.mockImplementation(async (_, fragment) => ({
    fragmentId: fragment.fragmentId,
    regionId: "region-" + fragment.fragmentId,
    createdEntityIds: ["region-" + fragment.fragmentId],
    insertedAtSeconds: 0,
  }));
  env.library = [sketch];
  env.fetchList.mockImplementation(() => ({ fragments: [...env.library] }));
  env.rank.mockImplementation((body) => ({
    request_id: "request", model_id: "rules-v1", fallback_used: false,
    candidates: body.candidates.map((c: { fragment_id: string }) => ({ ...c, score: 1, evidence: [] })),
  }));
  env.download.mockResolvedValue(new Blob(["audio"]));
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    if (path === "/api/ingest") env.library.push(sketch);
    return new Response(new Blob(["audio"]));
  }));
  vi.stubGlobal("Audio", class { play = env.play; pause = env.pause; });
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL() { return "blob:preview"; }
    static revokeObjectURL() {}
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("ranks the first imported sample without leaving the session", async () => {
  env.library = [];
  render(<AudiotoolPage />);
  await waitFor(() => expect(env.fetchList).toHaveBeenCalled());
  fireEvent.click(screen.getAllByRole("button", { name: /import samples to library/i })[0]);
  await screen.findByText(/Imported 1 of 1/);
  fireEvent.click(await suggest());
  expect(await screen.findByText("Sketch")).toBeInTheDocument();
});

it("allows another attempt when every download fails", async () => {
  env.download.mockResolvedValue(new Error("download failed"));
  render(<AudiotoolPage />);
  await suggest();
  fireEvent.click(screen.getByRole("button", { name: /import samples to library/i }));
  await screen.findByText(/Imported 0 of 1/);
  expect(screen.getByRole("button", { name: /import samples to library/i })).toBeEnabled();
});

it("keeps undo and ranking context inside the project where the insert happened", async () => {
  const ui = render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  fireEvent.click(await screen.findByRole("button", { name: /insert/i }));
  await screen.findByRole("button", { name: "Undo" });
  env.project = "";
  ui.rerender(<AudiotoolPage />);
  env.project = "B";
  ui.rerender(<AudiotoolPage />);
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  fireEvent.click(await suggest());
  await waitFor(() => expect(env.rank).toHaveBeenLastCalledWith(expect.objectContaining({
    session: expect.objectContaining({ project_id: "B", context_tags: [] }),
  })));
});

it("plays previews after Strict Mode replays the mount effect", async () => {
  render(<StrictMode><AudiotoolPage /></StrictMode>);
  fireEvent.click(await suggest());
  fireEvent.click(await screen.findByRole("button", { name: /preview/i }));
  await waitFor(() => expect(env.play).toHaveBeenCalledOnce());
});

it("can rank an older library page without combining scores from different pools", async () => {
  const older = { ...sketch, _id: "older", title: "Older sketch" };
  env.fetchList.mockImplementation((path: string) => path.includes("before=")
    ? { fragments: [older], next_cursor: null }
    : { fragments: [sketch], next_cursor: "older-page" });
  render(<AudiotoolPage />);
  fireEvent.click(await screen.findByRole("button", { name: /older sketches/i }));
  fireEvent.click(await suggest());
  expect(await screen.findByText("Older sketch")).toBeInTheDocument();
  expect(env.rank.mock.lastCall?.[0].candidates.map((c: { fragment_id: string }) => c.fragment_id)).toEqual(["older"]);
});

it("checks the live document before applying an outstanding undo receipt", async () => {
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  fireEvent.click(await screen.findByRole("button", { name: /insert/i }));
  const undo = await screen.findByRole("button", { name: "Undo" });
  // The SDK can change documents before React has rendered the new project.
  env.project = "B";
  fireEvent.click(undo);
  expect(env.undo).not.toHaveBeenCalled();
  env.project = "A";
  fireEvent.click(undo);
  await waitFor(() => expect(env.undo).toHaveBeenCalledOnce());
});

it("stops a pending sample import when its project closes", async () => {
  let finishDownload!: (blob: Blob) => void;
  env.download.mockReturnValue(new Promise<Blob>((resolve) => { finishDownload = resolve; }));
  const ui = render(<AudiotoolPage />);
  await suggest();
  fireEvent.click(screen.getByRole("button", { name: /import samples to library/i }));
  await waitFor(() => expect(env.download).toHaveBeenCalledOnce());
  env.project = "";
  ui.rerender(<AudiotoolPage />);
  await act(async () => { finishDownload(new Blob(["wav"])); });
  expect(vi.mocked(fetch).mock.calls.map(([url]) => url)).not.toContain("/api/ingest");
});

const parsed = { tags: [], roles: [], bpm: null, key: "e minor" };

function pagedLibrary() {
  env.fetchList.mockImplementation((path: string) => ({
    fragments: [sketch],
    next_cursor: path.includes("before=") ? null : "older-page",
  }));
}

it("keeps the chosen ranker and count but clears previous results when paging", async () => {
  pagedLibrary();
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  await screen.findByText("Sketch");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "text-only-v1" } });
  fireEvent.click(screen.getByRole("radio", { name: "Explore" }));
  fireEvent.click(screen.getByRole("button", { name: "Older sketches" }));
  const rankPage = await screen.findByRole("button", { name: "Explore 6" });
  // Adjacent pages deliberately contain the same ID. Ranks belong to one pool.
  expect(screen.queryByText("Sketch")).toBeNull();
  fireEvent.click(rankPage);
  expect(env.rank.mock.lastCall?.[0]).toMatchObject({ model_id: "text-only-v1", limit: 6 });
});

it("does not reparse a reviewed intent after the library page changes", async () => {
  pagedLibrary();
  env.parse.mockResolvedValue({ parsed });
  render(<AudiotoolPage />);
  await suggest();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "in E minor" } });
  fireEvent.click(await screen.findByRole("button", { name: "Remove e minor" }, { timeout: 3000 }));
  fireEvent.click(screen.getByRole("button", { name: "Older sketches" }));
  await suggest();
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 950)); });
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].session.parsed_intent).toBeNull();
  expect(env.parse).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: "Remove e minor" })).toBeNull();
});

it("ignores a delayed interpretation after the musician clears the text", async () => {
  let finish!: (value: { parsed: typeof parsed }) => void;
  env.parse.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  render(<AudiotoolPage />);
  await suggest();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "in E minor" } });
  await waitFor(() => expect(env.parse).toHaveBeenCalledOnce(), { timeout: 3000 });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "" } });
  await act(async () => finish({ parsed }));
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].session).toMatchObject({ text_intent: "", parsed_intent: null });
});

it("clears the old interpretation as soon as different text is entered", async () => {
  env.parse.mockResolvedValue({ parsed });
  render(<AudiotoolPage />);
  await suggest();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "in E minor" } });
  await screen.findByRole("button", { name: "Remove e minor" }, { timeout: 3000 });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "something else" } });
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].session).toMatchObject({ text_intent: "something else", parsed_intent: null });
});

it("locks insertions during undo and keeps the next receipt and its tags", async () => {
  env.library.push({ ...sketch, _id: "b", title: "Drums", tags: ["drums"] });
  let finish!: () => void;
  env.undo.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  fireEvent.click((await screen.findAllByRole("button", { name: /insert into/i }))[0]);
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  const nextInsert = screen.getAllByRole("button", { name: /insert into/i })[1];
  expect(nextInsert).toBeDisabled();
  fireEvent.click(nextInsert);
  expect(env.insert).toHaveBeenCalledTimes(1);
  await act(async () => finish());
  fireEvent.click(nextInsert);
  await screen.findByText(/Inserted “Drums”/);
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].session.context_tags).toEqual(["drums"]);
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(env.undo.mock.lastCall?.at(-1)).toMatchObject({ regionId: "region-b" }));
});

it("records every choice, and identifies the inserted copy on insert and undo", async () => {
  env.insert.mockRejectedValueOnce(new Error("Audio upload failed"));
  let finishLink!: () => void;
  env.link.mockReturnValueOnce(new Promise<void>((resolve) => { finishLink = resolve; }));
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  const insert = await screen.findByRole("button", { name: /insert into/i });
  fireEvent.click(insert);
  await screen.findByText("Audio upload failed");
  await waitFor(() => expect(env.events.mock.calls.map(([event]) => event.event)).toEqual(["accept"]));
  fireEvent.click(insert);
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await waitFor(() => expect(env.events.mock.calls.map(([event]) => event.event)).toEqual(["accept", "accept", "insert", "undo"]));
  expect(env.events.mock.calls.map(([event]) => event.insertion_id))
    .toEqual([undefined, undefined, "region-f", "region-f"]);
  expect(env.link).toHaveBeenCalledWith(expect.objectContaining({ insertion_id: "region-f" }));
  expect(env.unlink).not.toHaveBeenCalled();
  await act(async () => finishLink());
  expect(env.unlink).toHaveBeenCalledWith(expect.objectContaining({ insertion_id: "region-f" }));
});

it("keeps a failed undo retriable and shows the SDK error", async () => {
  env.undo.mockRejectedValueOnce(new Error("Region has dependents"));
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  fireEvent.click(await screen.findByRole("button", { name: /insert into/i }));
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Region has dependents");
  const undo = screen.getByRole("button", { name: "Undo" });
  expect(undo).toBeEnabled();
  fireEvent.click(undo);
  await waitFor(() => expect(screen.queryByRole("button", { name: "Undo" })).toBeNull());
});

it("preserves spaces as the musician types a multiword intent", async () => {
  render(<AudiotoolPage />);
  await suggest();
  const input = screen.getByRole("textbox");
  await userEvent.type(input, "in E minor ");
  expect(input).toHaveValue("in E minor ");
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].session.text_intent).toBe("in E minor");
});

it("keeps reviewed chips when only the surrounding whitespace changes", async () => {
  env.parse.mockResolvedValue({ parsed: { ...parsed, tags: ["quiet"] } });
  render(<AudiotoolPage />);
  await suggest();
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "in E minor" } });
  fireEvent.click(await screen.findByRole("button", { name: "Remove quiet" }, { timeout: 3000 }));
  fireEvent.change(input, { target: { value: " in E minor " } });
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].session.parsed_intent).toEqual(parsed);
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 900)); });
  expect(env.parse).toHaveBeenCalledOnce();
  expect(screen.queryByRole("button", { name: "Remove quiet" })).toBeNull();
});

it("keeps playing the last preview selected when an earlier download arrives late", async () => {
  let finish!: (response: Response) => void;
  vi.mocked(fetch).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  env.library.push({ ...sketch, _id: "b", title: "Drums" });
  const createUrl = vi.spyOn(URL, "createObjectURL");
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  const [first, second] = await screen.findAllByRole("button", { name: "Preview" });
  fireEvent.click(first);
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  fireEvent.click(second);
  await waitFor(() => expect(env.play).toHaveBeenCalledOnce());
  await act(async () => { finish(new Response(new Blob(["older preview"]))); });
  expect(env.play).toHaveBeenCalledOnce();
  expect(env.pause).not.toHaveBeenCalled();
  expect(createUrl).toHaveBeenCalledOnce();
});

it("stops a playing preview on pagination and drops its pending replacement on unmount", async () => {
  pagedLibrary();
  const revoke = vi.spyOn(URL, "revokeObjectURL");
  const ui = render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  fireEvent.click(await screen.findByRole("button", { name: "Preview" }));
  await waitFor(() => expect(env.play).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole("button", { name: "Older sketches" }));
  await suggest();
  expect(env.pause).toHaveBeenCalledOnce();
  expect(revoke).toHaveBeenCalledOnce();

  let finish!: (response: Response) => void;
  vi.mocked(fetch).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  fireEvent.click(await suggest());
  fireEvent.click(await screen.findByRole("button", { name: "Preview" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  ui.unmount();
  await act(async () => { finish(new Response(new Blob(["abandoned preview"]))); });
  expect(env.play).toHaveBeenCalledOnce();
});

it("shows a playback failure, releases the URL and lets the musician retry", async () => {
  env.play.mockRejectedValueOnce(new Error("Playback blocked"));
  const revoke = vi.spyOn(URL, "revokeObjectURL");
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  const preview = await screen.findByRole("button", { name: "Preview" });
  fireEvent.click(preview);
  expect(await screen.findByRole("alert")).toHaveTextContent(/preview.*Sketch/i);
  expect(revoke).toHaveBeenCalledOnce();
  fireEvent.click(preview);
  await waitFor(() => expect(env.play).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("alert")).toBeNull();
});

it("ignores a superseded playback rejection and releases the current URL when playback ends", async () => {
  let rejectFirst!: (reason: Error) => void;
  env.play.mockReturnValueOnce(new Promise<void>((_, reject) => { rejectFirst = reject; }));
  const players: { onended: (() => void) | null }[] = [];
  vi.stubGlobal("Audio", class {
    onended: (() => void) | null = null;
    constructor() { players.push(this); }
    play = env.play;
    pause = env.pause;
  });
  vi.spyOn(URL, "createObjectURL").mockReturnValueOnce("blob:first").mockReturnValueOnce("blob:second");
  const revoke = vi.spyOn(URL, "revokeObjectURL");
  const ui = render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  const preview = await screen.findByRole("button", { name: "Preview" });
  fireEvent.click(preview);
  await waitFor(() => expect(env.play).toHaveBeenCalledOnce());
  fireEvent.click(preview);
  await waitFor(() => expect(env.play).toHaveBeenCalledTimes(2));
  await act(async () => { rejectFirst(new Error("Playback interrupted")); });
  expect(screen.queryByRole("alert")).toBeNull();
  expect(revoke.mock.calls).toEqual([["blob:first"]]);
  act(() => { players[1].onended?.(); });
  ui.unmount();
  expect(revoke.mock.calls).toEqual([["blob:first"], ["blob:second"]]);
});

it("excludes skipped fragments from the next ranking request", async () => {
  env.library.push({ ...sketch, _id: "b", title: "Drums" });
  render(<AudiotoolPage />);
  fireEvent.click(await suggest());
  fireEvent.click((await screen.findAllByRole("button", { name: "Skip" }))[0]);
  fireEvent.click(await suggest());
  expect(env.rank.mock.lastCall?.[0].candidates.map((c: { fragment_id: string }) => c.fragment_id)).toEqual(["b"]);
});

it("reconsiders skipped fragments after the musician removes an intent chip", async () => {
  env.library.push({ ...sketch, _id: "b", title: "Drums" });
  env.parse.mockResolvedValue({ parsed });
  render(<AudiotoolPage />);
  await suggest();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "in E minor" } });
  const removeKey = await screen.findByRole("button", { name: "Remove e minor" }, { timeout: 3000 });
  fireEvent.click(await suggest());
  fireEvent.click((await screen.findAllByRole("button", { name: "Skip" }))[0]);
  fireEvent.click(removeKey);
  fireEvent.click(await suggest());
  const request = env.rank.mock.lastCall?.[0];
  expect(request.session.parsed_intent).toBeNull();
  expect(request.candidates.map((c: { fragment_id: string }) => c.fragment_id)).toEqual(["f", "b"]);
});
