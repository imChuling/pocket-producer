// Upload a fragment's audio as an Audiotool sample and insert it into the
// open project — reversibly.
//
// Order is strict: the document is only modified after the sample bytes are
// acknowledged by the server, so a failed upload never leaves a broken
// sample entity in the user's project. The insert happens in one Nexus
// transaction; on failure no partial timeline state exists. The receipt
// records every created entity so undo removes exactly this insertion.

import { secondsToTicks } from "@audiotool/nexus/utils";

export type InsertReceipt = {
  regionId: string;
  createdEntityIds: string[];
  fragmentId: string;
  insertedAtSeconds: number;
};

type EntityLike = { id: string };

type TransactionLike = {
  entities: { get: () => EntityLike[] };
  insertSample: (
    sample: { name: string; durationSeconds: number; bpm?: number },
    options?: {
      sample?: { bpm?: number | "project" };
      region?: { positionTicks?: number };
      displayName?: string;
    },
  ) => EntityLike;
  removeWithDependencies: (id: string) => void;
};

type DocumentLike = {
  modify: <T>(fn: (t: TransactionLike) => T) => Promise<T>;
};

type SampleUploadLike = {
  name: string;
  uploaded: Promise<void | Error>;
};

type SamplesLike = {
  upload: (options: {
    file: Blob;
    displayName: string;
    bpm?: number;
  }) => Promise<SampleUploadLike | Error>;
};

export type InsertDeps = {
  samples: SamplesLike;
  document: DocumentLike;
};

export type InsertableFragment = {
  fragmentId: string;
  title: string;
  durationSeconds: number;
  bpm: number | null;
};

const DEFAULT_BPM = 120;

export async function insertFragment(
  deps: InsertDeps,
  fragment: InsertableFragment,
  options: {
    audioBlob: Blob;
    playheadSeconds: number;
    projectBpm: number | null;
  },
): Promise<InsertReceipt> {
  const upload = await deps.samples.upload({
    file: options.audioBlob,
    displayName: fragment.title,
    ...(fragment.bpm !== null ? { bpm: fragment.bpm } : {}),
  });
  if (upload instanceof Error) throw upload;

  const uploaded = await upload.uploaded;
  if (uploaded instanceof Error) throw uploaded;

  // Audiotool maps samples to musical time, so a bpm is always needed;
  // preference order: project tempo, fragment tempo, then a documented default.
  const bpm = options.projectBpm ?? fragment.bpm ?? DEFAULT_BPM;
  const positionTicks = Math.max(
    0,
    Math.round(secondsToTicks(options.playheadSeconds, bpm)),
  );

  return deps.document.modify((t) => {
    const idsBefore = new Set(t.entities.get().map((entity) => entity.id));
    const region = t.insertSample(
      {
        name: upload.name,
        durationSeconds: fragment.durationSeconds,
        ...(fragment.bpm !== null ? { bpm: fragment.bpm } : {}),
      },
      {
        sample: { bpm },
        region: { positionTicks },
        displayName: fragment.title,
      },
    );
    const createdEntityIds = t.entities
      .get()
      .map((entity) => entity.id)
      .filter((id) => !idsBefore.has(id));
    return {
      regionId: region.id,
      createdEntityIds,
      fragmentId: fragment.fragmentId,
      insertedAtSeconds: options.playheadSeconds,
    };
  });
}

export async function undoInsert(
  document: DocumentLike,
  receipt: InsertReceipt,
): Promise<void> {
  await document.modify((t) => {
    const created = new Set(receipt.createdEntityIds);
    // Remove dependents first so no removal ever leaves dangling pointers.
    for (const id of [...receipt.createdEntityIds].reverse()) {
      const stillExists = t.entities
        .get()
        .some((entity) => entity.id === id && created.has(id));
      if (stillExists) t.removeWithDependencies(id);
    }
  });
}
