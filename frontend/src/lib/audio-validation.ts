import { MAX_AUDIO_DURATION_SEC } from "./constants";

export async function validateAudioDuration(
  file: File,
): Promise<{ valid: boolean; duration: number; error?: string }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    const cleanup = () => {
      URL.revokeObjectURL(url);
      audio.removeAttribute("src");
      audio.load();
    };

    audio.addEventListener("loadedmetadata", () => {
      const duration = audio.duration;
      cleanup();
      if (!isFinite(duration) || isNaN(duration)) {
        resolve({ valid: true, duration: 0 });
        return;
      }
      if (duration > MAX_AUDIO_DURATION_SEC) {
        resolve({
          valid: false,
          duration,
          error: `Audio too long (${Math.ceil(duration / 60)} min). Max 5 minutes.`,
        });
        return;
      }
      resolve({ valid: true, duration });
    });

    audio.addEventListener("error", () => {
      cleanup();
      resolve({ valid: true, duration: 0 });
    });

    audio.src = url;
  });
}
