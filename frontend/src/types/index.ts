export interface EditHistoryEntry {
  id: string;
  text: string;
  edited_at: string;
}

export interface Fragment {
  _id: string;
  user_id: string;
  type: "audio" | "text";
  status?: "processing" | "ready" | "error" | "timeout";
  title?: string;
  text?: string;
  raw_text?: string;
  audio_url?: string;
  tags: string[];
  emotions: string[];
  themes: string[];
  style?: string[];
  structure_hint?: string;
  potential?: "high" | "medium" | "low";
  key?: string;
  bpm?: number;
  embedding?: number[];
  suggestion?: string;
  project_id?: string;
  project_title?: string;
  connection_reason?: string;
  connection_types?: string[];
  agent_narrative?: string;
  notes?: string;
  user_edited_fields?: string[];
  agent_result?: string;
  edit_history?: EditHistoryEntry[];
  created_at: string;
}

export interface ScoreBreakdown {
  richness: number;
  structure_completeness: number;
  emotional_coherence: number;
  freshness: number;
}

export interface NextAction {
  action: string;
  estimated_time?: string;
}

export interface Project {
  _id: string;
  user_id: string;
  title: string;
  rescue_score: number | null;
  score_breakdown?: ScoreBreakdown;
  next_action?: NextAction;
  fragment_ids: string[];
  sections: string[];
  connection_reasons?: string[];
  connection_types?: string[];
  last_activity_at: string;
  created_at: string;
}

export interface ProjectDetail extends Project {
  fragments: Fragment[];
}

export interface DNAData {
  user_id: string;
  emotions: Record<string, number>;
  themes: Record<string, number>;
  hourly_distribution: Record<string, number>;
  total_fragments: number;
  total_projects: number;
  dominant_emotion?: string;
  top_styles?: { _id: string; count: number }[];
  structure_distribution?: { _id: string; count: number }[];
  emotion_timeline?: { week: string; emotions: Record<string, number> }[];
  peak_hours?: string;
  updated_at: string;
}

export interface NetworkNode {
  id: string;
  title: string;
  type: "audio" | "text";
  emotions: string[];
  project_id?: string;
  project_title?: string;
}

export interface NetworkEdge {
  source: string;
  target: string;
  project_id: string;
  project_title: string;
}

export interface NetworkData {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

export interface Notification {
  _id: string;
  type: "resurrect";
  new_fragment_id: string;
  new_fragment_title?: string;
  sleeping_project_id: string;
  sleeping_project_title?: string;
  similarity_score: number;
  message?: string;
  created_at: string;
  read: boolean;
}
