import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function PrivacyPage() {
  return (
    <div className="relative min-h-[calc(100vh-56px)]">
      <div className="ambient-mesh" />
      <div className="relative z-10 max-w-[720px] mx-auto px-6 py-12 animate-page-enter">
        <div className="flex items-center gap-3 mb-8">
          <Link
            href="/"
            className="p-2 -ml-2 rounded-full hover:bg-powder transition-colors cursor-pointer btn-press"
            aria-label="Back"
          >
            <ArrowLeft size={18} className="text-gravel" />
          </Link>
          <h1 className="font-heading text-3xl font-light tracking-tight shimmer-heading">
            Privacy Policy
          </h1>
        </div>
        <div className="prose-sm space-y-6 text-gravel text-[13px] leading-relaxed">
          <p className="text-slate text-xs">Last updated: June 2026</p>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">What We Collect</h2>
            <p>
              Pocket Producer collects the creative content you choose to share: audio recordings, lyrics,
              text notes, and voice memos. We also generate metadata from your content, including emotional
              tags, thematic labels, musical features (key, tempo), and embedding vectors used for similarity
              search.
            </p>
            <p>
              We collect your Firebase authentication identifier (UID) to associate your data with your
              account. We do not collect your name, email address, or other personal identifiers beyond
              what Firebase Authentication provides.
            </p>
          </section>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">How We Use Your Data</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>Analyze and tag your music fragments using AI models</li>
              <li>Find connections between your fragments via vector similarity search</li>
              <li>Assemble related fragments into projects with rescue scores</li>
              <li>Generate your Creative DNA profile (aggregated from your own data only)</li>
              <li>Provide personalized next-action suggestions</li>
            </ul>
            <p>
              Your creative content is never used to train AI models. It is processed solely to provide
              the features described above.
            </p>
          </section>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">Third-Party Processors</h2>
            <p>Your data is processed by the following services, each under their own privacy policies:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Google Cloud Platform</strong> (Vertex AI, Cloud Run, Cloud Storage) &mdash; AI inference, hosting, audio file storage</li>
              <li><strong>MongoDB Atlas</strong> &mdash; database storage, vector search</li>
              <li><strong>Voyage AI</strong> (MongoDB-provided) &mdash; text embedding generation</li>
              <li><strong>Firebase Authentication</strong> &mdash; user identity verification</li>
            </ul>
            <p>
              All data is stored in the <strong>us-central1</strong> region. No data is shared with
              third parties for advertising, analytics, or any purpose beyond operating this service.
            </p>
          </section>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">Data Retention</h2>
            <p>
              Your data is retained for as long as your account exists. Audio recordings are stored in
              Google Cloud Storage; all other data is stored in MongoDB Atlas. There is no automatic
              expiration or deletion schedule.
            </p>
          </section>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">Your Rights</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Delete individual fragments</strong> &mdash; available from any fragment card</li>
              <li><strong>Delete your entire account</strong> &mdash; available in Settings; this permanently
                removes all your fragments, projects, DNA data, notification history, settings, and
                audio files from our systems</li>
              <li><strong>Data portability</strong> &mdash; contact us to request an export of your data</li>
            </ul>
            <p>
              Deletion is immediate and irreversible. We do not retain backups of deleted user data.
            </p>
          </section>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">Sensitive Data</h2>
            <p>
              Audio recordings and lyrics may contain personal expression. We treat all creative content
              as sensitive personal data. Access is scoped to your authenticated account only &mdash; no
              other user or administrator can view your content through the application.
            </p>
          </section>

          <section>
            <h2 className="font-heading text-base font-medium text-obsidian mb-2">Contact</h2>
            <p>
              For privacy questions or data requests, contact us at{" "}
              <span className="text-obsidian">privacy@pocketproducer.app</span>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
