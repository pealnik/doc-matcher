import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { Clock, CheckCircle, XCircle, Download } from "lucide-react";
import { ComplianceTable } from "./ComplianceTable";
import type { TaskStatus } from "../lib/api";

interface TaskProgressProps {
  task: TaskStatus;
}

export function TaskProgress({ task }: TaskProgressProps) {
  const handleDownloadPDF = async () => {
    try {
      const API_BASE_URL =
        import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${API_BASE_URL}/tasks/${task.task_id}/download`
      );

      if (!response.ok) {
        throw new Error("Failed to download PDF");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `compliance_report_${task.task_id}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Error downloading PDF:", error);
      alert("Failed to download PDF report");
    }
  };

  const handleCancelTask = async () => {
    if (!task.task_id) return;
    try {
      const API_BASE_URL =
        import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${API_BASE_URL}/tasks/${task.task_id}/cancel`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to cancel task");
      }

      alert(
        `Cancellation requested for task ${task.task_id}. The status will update shortly.`
      );
      // The SSE stream will automatically update the task status in the UI
    } catch (err: unknown) {
      console.error("Error cancelling task:", err);
      const message = err instanceof Error ? err.message : String(err);
      alert(`Failed to cancel task: ${message}`);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Task Status</CardTitle>
          <div className="flex items-center gap-2">
            {task.status === "completed" &&
              task.result?.rows &&
              task.result.rows.length > 0 && (
                <Button onClick={handleDownloadPDF} variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Download PDF
                </Button>
              )}
            {task.status === "processing" && (
              <Button
                onClick={handleCancelTask}
                variant="destructive"
                size="sm"
              >
                <XCircle className="h-4 w-4 mr-2" />
                Stop Task
              </Button>
            )}
            <Badge
              variant={
                task.status === "completed"
                  ? "default"
                  : task.status === "failed"
                  ? "destructive"
                  : "secondary"
              }
            >
              {task.status === "pending" && <Clock className="h-3 w-3 mr-1" />}
              {task.status === "processing" && (
                <Clock className="h-3 w-3 mr-1 animate-spin" />
              )}
              {task.status === "completed" && (
                <CheckCircle className="h-3 w-3 mr-1" />
              )}
              {task.status === "failed" && <XCircle className="h-3 w-3 mr-1" />}
              {task.status}
            </Badge>
          </div>
        </div>
        <CardDescription>{task.message}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {task.status !== "failed" && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Progress</span>
              <span>{task.progress}%</span>
            </div>
            <Progress value={task.progress} />
          </div>
        )}

        {(task.status === "processing" || task.status === "completed") && (
          <div className="space-y-4 mt-6">
            <div className="grid grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold text-green-600">
                    {task.result?.summary.total_compliant ??
                      task.result?.summary.compliant ??
                      0}
                  </div>
                  <div className="text-sm text-gray-600">Compliant</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold text-red-600">
                    {task.result?.summary.total_non_compliant ??
                      task.result?.summary.non_compliant ??
                      0}
                  </div>
                  <div className="text-sm text-gray-600">Non-Compliant</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold text-orange-600">
                    {task.result?.summary.total_partial ??
                      task.result?.summary.partially_compliant ??
                      0}
                  </div>
                  <div className="text-sm text-gray-600">
                    Partially Compliant
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-2xl font-bold">
                    {task.result?.summary.total_rows ??
                      task.result?.summary.total ??
                      0}
                  </div>
                  <div className="text-sm text-gray-600">Total Checks</div>
                </CardContent>
              </Card>
            </div>

            <ComplianceTable
              rows={task.result?.rows || []}
              isProcessing={task.status === "processing"}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
