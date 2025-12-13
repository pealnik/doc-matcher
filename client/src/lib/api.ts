const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface Guideline {
  id: string;
  filename: string;
  uploaded_at: string;
  size: number;
  pages?: number; // Represents total_requirements for checklists
  vectorstore_ready?: boolean;
  description?: string; // Checklist name
}

export interface ChecklistRequirement {
  id: string;
  requirement: string;
  regulation_source: string;
  category: string;
  expected_fields: string[];
  check_type: string;
  search_keywords: string[];
  severity: string;
}

export interface ChecklistDetails {
  checklist_name: string;
  version: string;
  last_updated: string;
  regulations: string[];
  total_requirements: number;
  requirements: ChecklistRequirement[];
}

export interface ComplianceRow {
  // Old fields (RAG-based rows)
  mepc_reference?: string;
  ihm_output?: string;
  // New fields (fixed-checklist rows)
  requirement_id?: string;
  requirement_text?: string;
  regulation_source?: string;
  evidence?: string;
  evidence_pages?: number[];
  category?: string;
  severity?: string;
  check_type?: string;

  // Common
  status: "Compliant" | "Non-Compliant" | "Partially Compliant" | "Error";
  remarks?: string;
  // Optional chunk/page range for backward compatibility
  chunk_start_page?: number;
  chunk_end_page?: number;
}

export interface TaskStatus {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  message: string;
  result?: {
    rows: ComplianceRow[];
    // Summary may come in two formats: { total_* } for backward compatibility, or { compliant, non_compliant, ... }
    summary: Record<string, number>;
    latest_row?: ComplianceRow;
  };
  created_at: string;
  updated_at: string;
}

export const api = {
  async uploadGuideline(file: File): Promise<Guideline> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE_URL}/guidelines/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to upload guideline");
    }

    return response.json();
  },

  async getGuidelines(): Promise<Guideline[]> {
    const response = await fetch(`${API_BASE_URL}/guidelines`);

    if (!response.ok) {
      throw new Error("Failed to fetch guidelines");
    }

    return response.json();
  },

  async deleteGuideline(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/guidelines/${id}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to delete guideline");
    }
  },

  async startMatch(report: File, guidelineIds: string[]): Promise<TaskStatus> {
    const formData = new FormData();
    formData.append("report", report);
    formData.append("guideline_ids", JSON.stringify(guidelineIds));

    const response = await fetch(`${API_BASE_URL}/match`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to start matching");
    }

    return response.json();
  },

  streamTaskStatus(
    taskId: string,
    onUpdate: (data: TaskStatus) => void
  ): EventSource {
    const eventSource = new EventSource(
      `${API_BASE_URL}/tasks/${taskId}/stream`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onUpdate(data);
    };

    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      eventSource.close();
    };

    return eventSource;
  },

  async getTasks(): Promise<TaskStatus[]> {
    const response = await fetch(`${API_BASE_URL}/tasks`);

    if (!response.ok) {
      throw new Error("Failed to fetch tasks");
    }

    return response.json();
  },

  async getChecklistDetails(id: string): Promise<ChecklistDetails> {
    const response = await fetch(`${API_BASE_URL}/guidelines/${id}/details`);

    if (!response.ok) {
      throw new Error("Failed to fetch checklist details");
    }

    return response.json();
  },
};
