"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "./use-auth";
import type { Project, ProjectDetail } from "@/types";

export function useProjects() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!user) return;
    apiFetch<{ projects: Project[] }>("/projects")
      .then((data) => setProjects(data.projects))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user, tick]);

  return { projects, loading, refresh };
}

export function useProjectDetail(id: string) {
  const { user } = useAuth();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    apiFetch<ProjectDetail>(`/projects/${id}`)
      .then(setProject)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user, id]);

  return { project, loading };
}
