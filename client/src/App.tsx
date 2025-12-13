import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { Alert, AlertDescription } from "./components/ui/alert";
import { AlertCircle, CheckCircle } from "lucide-react";
import { api } from "./lib/api";
import type { Guideline, TaskStatus } from "./lib/api";
import { GuidelineList } from "./components/GuidelineList";
import { ReportUpload } from "./components/ReportUpload";
import { TaskProgress } from "./components/TaskProgress";
import { ChecklistView } from "./components/ChecklistView";

function HomePage() {
  const navigate = useNavigate();
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  const [selectedGuidelines, setSelectedGuidelines] = useState<string[]>([]);
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadGuidelines();
  }, []);

  useEffect(() => {
    if (
      currentTask &&
      (currentTask.status === "pending" || currentTask.status === "processing")
    ) {
      console.log("🔥 Starting SSE stream for task:", currentTask.task_id);

      const eventSource = api.streamTaskStatus(
        currentTask.task_id,
        (updated) => {
          console.log("📊 Task update (SSE):", {
            status: updated.status,
            progress: updated.progress,
            rowCount: updated.result?.rows?.length || 0,
            message: updated.message,
          });
          setCurrentTask((prev) => {
            if (!prev) return updated; // Should not happen with an existing currentTask

            const newResult = prev.result
              ? { ...prev.result }
              : { rows: [], summary: {} };

            // Handle incremental updates during processing
            if (updated.status === "processing" && updated.result?.latest_row) {
              // Append the latest row
              newResult.rows = [...newResult.rows, updated.result.latest_row];
              // Update summary
              newResult.summary = updated.result.summary || newResult.summary;
            } else if (updated.result) {
              // For completed/failed tasks, or initial result, replace rows and summary
              newResult.rows = updated.result.rows || newResult.rows;
              newResult.summary = updated.result.summary || newResult.summary;
            }

            return {
              ...prev,
              ...updated,
              result: newResult,
              // Ensure task_id and created_at are preserved if not in update
              task_id: prev.task_id,
              created_at: prev.created_at,
            };
          });

          if (updated.status === "completed" || updated.status === "failed") {
            console.log("✅ Task finished, closing SSE stream");
            eventSource.close();
          }
        }
      );

      return () => {
        console.log("🛑 Closing SSE stream");
        eventSource.close();
      };
    }
  }, [currentTask?.task_id]);

  // Poll for guideline indexing status
  useEffect(() => {
    const hasIndexingGuidelines = guidelines.some(
      (g) => g.vectorstore_ready === false
    );

    if (hasIndexingGuidelines) {
      const interval = setInterval(async () => {
        try {
          await loadGuidelines();
        } catch (err) {
          console.error("Error polling guidelines:", err);
        }
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [guidelines]);

  const loadGuidelines = async () => {
    try {
      const data = await api.getGuidelines();
      const availableGuidelines = data.filter(
        (g) => g.vectorstore_ready === true || g.vectorstore_ready === false
      );
      setGuidelines(availableGuidelines);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load guidelines"
      );
    }
  };

  const handleGuidelineUpload = async (file: File) => {
    setError(null);
    setSuccess(null);

    try {
      await api.uploadGuideline(file);
      setSuccess(`Successfully uploaded ${file.name}`);
      await loadGuidelines();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to upload guideline"
      );
      throw err;
    }
  };

  const handleGuidelineDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this guideline?")) return;

    try {
      await api.deleteGuideline(id);
      setSuccess("Guideline deleted successfully");
      setSelectedGuidelines((prev) => prev.filter((gid) => gid !== id));
      await loadGuidelines();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete guideline"
      );
      throw err;
    }
  };

  const toggleGuideline = (id: string) => {
    setSelectedGuidelines((prev) =>
      prev.includes(id) ? prev.filter((gid) => gid !== id) : [...prev, id]
    );
  };

  const handleStartMatch = async (reportFile: File) => {
    if (selectedGuidelines.length === 0) {
      setError("Please select at least one guideline");
      throw new Error("No guidelines selected");
    }

    setError(null);
    setSuccess(null);

    try {
      const task = await api.startMatch(reportFile, selectedGuidelines);
      setCurrentTask(task);
      setSuccess("Matching started! Monitor progress below.");
      console.log("Task created:", task.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start matching");
      throw err;
    }
  };

  const handleViewChecklist = (id: string) => {
    navigate(`/checklist/${id}`);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 relative">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8 flex items-center gap-3">
          <img src="/autolinium.svg" alt="Logo" className="h-12 w-12" />
          <a
            href="https://autolinium.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-gray-600 hover:text-gray-900"
          >
            Developed by Autolinium.com
          </a>
        </div>

        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900">
            PDF Compliance Checker
          </h1>
          <p className="text-gray-600 mt-2">
            Upload guidelines and check reports for compliance
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert className="mb-6 border-green-500 text-green-700">
            <CheckCircle className="h-4 w-4" />
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <GuidelineList
              guidelines={guidelines}
              selectedGuidelines={selectedGuidelines}
              onGuidelineUpload={handleGuidelineUpload}
              onGuidelineDelete={handleGuidelineDelete}
              onGuidelineToggle={toggleGuideline}
              onViewChecklist={handleViewChecklist}
            />
          </div>

          <div className="lg:col-span-2 space-y-6">
            <ReportUpload
              selectedGuidelinesCount={selectedGuidelines.length}
              onStartMatch={handleStartMatch}
            />

            {currentTask && <TaskProgress task={currentTask} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/checklist/:id" element={<ChecklistView />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
