import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 px-6">
      <h2 className="font-heading text-2xl text-obsidian">Page not found</h2>
      <p className="text-sm text-gravel">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link
        href="/"
        className="px-5 py-2 rounded-full bg-obsidian text-white text-xs font-mono tracking-wider hover:bg-obsidian/90 transition-colors btn-press"
      >
        Back to home
      </Link>
    </div>
  );
}
