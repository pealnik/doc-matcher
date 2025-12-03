const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface Guideline {
  id: string;
  filename: string;
  uploaded_at: string;
  size: number;
  pages?: number;
  vectorstore_ready?: boolean;
}

export interface ComplianceRow {
  mepc_reference: string;
  ihm_output: string;
  status: "Compliant" | "Non-Compliant" | "Partially Compliant";
  remarks: string;
  chunk_start_page: number;
  chunk_end_page: number;
}

export interface TaskStatus {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  message: string;
  result?: {
    rows: ComplianceRow[];
    summary: {
      total_rows: number;
      total_compliant: number;
      total_non_compliant: number;
      total_partial: number;
      total_chunks: number;
      total_pages: number;
    };
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

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to get task status");
    }

    return response.json();
  },

  async getTasks(): Promise<TaskStatus[]> {
    const response = await fetch(`${API_BASE_URL}/tasks`);

    if (!response.ok) {
      throw new Error("Failed to fetch tasks");
    }

    return response.json();
  },
};
