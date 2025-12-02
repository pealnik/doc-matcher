import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";
import { Progress } from "./components/ui/progress";
import { Badge } from "./components/ui/badge";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Checkbox } from "./components/ui/checkbox";
import { api } from "./lib/api";
import type { Guideline, TaskStatus } from "./lib/api";
import {
  Upload,
  Trash2,
  FileText,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
} from "lucide-react";

function App() {
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  const [selectedGuidelines, setSelectedGuidelines] = useState<string[]>([]);
  const [uploadingGuideline, setUploadingGuideline] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [reportFile, setReportFile] = useState<File | null>(null);
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
      const interval = setInterval(async () => {
        try {
          const updated = await api.getTaskStatus(currentTask.task_id);
          setCurrentTask(updated);

          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(interval);
          }
        } catch (err) {
          console.error("Error polling task:", err);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [currentTask]);

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
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(interval);
    }
  }, [guidelines]);

  const loadGuidelines = async () => {
    try {
      const data = await api.getGuidelines();
      // Only show guidelines that are ready or still indexing
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

  const handleGuidelineUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingGuideline(true);
    setError(null);
    setSuccess(null);
    setUploadProgress(0);

    try {
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 200);

      await api.uploadGuideline(file);

      clearInterval(progressInterval);
      setUploadProgress(100);

      setSuccess(`Successfully uploaded ${file.name}`);
      await loadGuidelines();

      e.target.value = "";
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to upload guideline"
      );
    } finally {
      setUploadingGuideline(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  };

  const handleDeleteGuideline = async (id: string) => {
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
    }
  };

  const handleReportSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setReportFile(file);
    }
  };

  const handleStartMatch = async () => {
    if (!reportFile) {
      setError("Please select a report file");
      return;
    }

    if (selectedGuidelines.length === 0) {
      setError("Please select at least one guideline");
      return;
    }

    setError(null);
    setSuccess(null);

    try {
      const task = await api.startMatch(reportFile, selectedGuidelines);
      setCurrentTask(task);
      setSuccess("Matching started! Monitor progress below.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start matching");
    }
  };

  const toggleGuideline = (id: string) => {
    setSelectedGuidelines((prev) =>
      prev.includes(id) ? prev.filter((gid) => gid !== id) : [...prev, id]
    );
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
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
            <Card>
              <CardHeader>
                <CardTitle>Guidelines</CardTitle>
                <CardDescription>
                  Upload and manage compliance guidelines
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="guideline-upload" className="cursor-pointer">
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-gray-400 transition-colors text-center">
                      <Upload className="mx-auto h-8 w-8 text-gray-400 mb-2" />
                      <span className="text-sm text-gray-600">
                        {uploadingGuideline
                          ? "Uploading..."
                          : "Click to upload guideline PDF"}
                      </span>
                      <Input
                        id="guideline-upload"
                        type="file"
                        accept=".pdf"
                        onChange={handleGuidelineUpload}
                        disabled={uploadingGuideline}
                        className="hidden"
                      />
                    </div>
                  </Label>
                  {uploadingGuideline && uploadProgress > 0 && (
                    <Progress value={uploadProgress} className="mt-2" />
                  )}
                </div>

                <div className="space-y-2">
                  <h3 className="font-semibold text-sm text-gray-700">
                    Available Guidelines ({guidelines.length})
                  </h3>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {guidelines.length === 0 ? (
                      <p className="text-sm text-gray-500 text-center py-4">
                        No guidelines uploaded yet
                      </p>
                    ) : (
                      guidelines.map((guideline) => (
                        <div
                          key={guideline.id}
                          className="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-start space-x-2 flex-1">
                              <Checkbox
                                id={guideline.id}
                                checked={selectedGuidelines.includes(
                                  guideline.id
                                )}
                                onCheckedChange={() =>
                                  toggleGuideline(guideline.id)
                                }
                              />
                              <div className="flex-1 min-w-0">
                                <label
                                  htmlFor={guideline.id}
                                  className="text-sm font-medium cursor-pointer block truncate"
                                >
                                  {guideline.filename}
                                </label>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  <Badge
                                    variant="secondary"
                                    className="text-xs"
                                  >
                                    {formatFileSize(guideline.size)}
                                  </Badge>
                                  {guideline.pages && (
                                    <Badge
                                      variant="secondary"
                                      className="text-xs"
                                    >
                                      {guideline.pages} pages
                                    </Badge>
                                  )}
                                  {guideline.vectorstore_ready === false && (
                                    <Badge
                                      variant="outline"
                                      className="text-xs text-yellow-600 border-yellow-600"
                                    >
                                      Indexing...
                                    </Badge>
                                  )}
                                  {guideline.vectorstore_ready === true && (
                                    <Badge
                                      variant="outline"
                                      className="text-xs text-green-600 border-green-600"
                                    >
                                      Ready
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                handleDeleteGuideline(guideline.id)
                              }
                              className="ml-2"
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Check Report</CardTitle>
                <CardDescription>
                  Upload a report to check against selected guidelines
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="report-upload">Report PDF</Label>
                  <div className="mt-2 flex items-center gap-4">
                    <Label
                      htmlFor="report-upload"
                      className="cursor-pointer flex-1"
                    >
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-gray-400 transition-colors">
                        <div className="flex items-center justify-center gap-2">
                          <FileText className="h-5 w-5 text-gray-400" />
                          <span className="text-sm text-gray-600">
                            {reportFile ? reportFile.name : "Select report PDF"}
                          </span>
                        </div>
                      </div>
                      <Input
                        id="report-upload"
                        type="file"
                        accept=".pdf"
                        onChange={handleReportSelect}
                        className="hidden"
                      />
                    </Label>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <div className="text-sm text-gray-600">
                    {selectedGuidelines.length > 0 ? (
                      <span>
                        {selectedGuidelines.length} guideline(s) selected
                      </span>
                    ) : (
                      <span className="text-orange-600">
                        Please select guidelines
                      </span>
                    )}
                  </div>
                  <Button
                    onClick={handleStartMatch}
                    disabled={!reportFile || selectedGuidelines.length === 0}
                    size="lg"
                  >
                    Start Matching
                  </Button>
                </div>
              </CardContent>
            </Card>

            {currentTask && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Task Status</CardTitle>
                    <Badge
                      variant={
                        currentTask.status === "completed"
                          ? "default"
                          : currentTask.status === "failed"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {currentTask.status === "pending" && (
                        <Clock className="h-3 w-3 mr-1" />
                      )}
                      {currentTask.status === "processing" && (
                        <Clock className="h-3 w-3 mr-1 animate-spin" />
                      )}
                      {currentTask.status === "completed" && (
                        <CheckCircle className="h-3 w-3 mr-1" />
                      )}
                      {currentTask.status === "failed" && (
                        <XCircle className="h-3 w-3 mr-1" />
                      )}
                      {currentTask.status}
                    </Badge>
                  </div>
                  <CardDescription>{currentTask.message}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {currentTask.status !== "failed" && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Progress</span>
                        <span>{currentTask.progress}%</span>
                      </div>
                      <Progress value={currentTask.progress} />
                    </div>
                  )}

                  {currentTask.result && (
                    <div className="space-y-4 mt-6">
                      <div className="grid grid-cols-3 gap-4">
                        <Card>
                          <CardContent className="pt-6">
                            <div className="text-2xl font-bold text-red-600">
                              {currentTask.result.summary.total_issues}
                            </div>
                            <div className="text-sm text-gray-600">
                              Total Issues
                            </div>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardContent className="pt-6">
                            <div className="text-2xl font-bold">
                              {currentTask.result.summary.total_chunks}
                            </div>
                            <div className="text-sm text-gray-600">
                              Chunks Analyzed
                            </div>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardContent className="pt-6">
                            <div className="text-2xl font-bold">
                              {currentTask.result.summary.total_pages}
                            </div>
                            <div className="text-sm text-gray-600">
                              Total Pages
                            </div>
                          </CardContent>
                        </Card>
                      </div>

                      <div className="space-y-3 max-h-96 overflow-y-auto">
                        <h3 className="font-semibold">Detailed Results</h3>
                        {currentTask.result.chunks.map((chunk, idx) => (
                          <Card
                            key={idx}
                            className="border-l-4"
                            style={{
                              borderLeftColor:
                                chunk.compliance === "compliant"
                                  ? "#10b981"
                                  : chunk.compliance === "non-compliant"
                                  ? "#ef4444"
                                  : "#f59e0b",
                            }}
                          >
                            <CardContent className="pt-4">
                              <div className="flex items-center justify-between mb-2">
                                <div className="font-medium">
                                  Pages {chunk.start_page}-{chunk.end_page}
                                </div>
                                <Badge
                                  variant={
                                    chunk.compliance === "compliant"
                                      ? "default"
                                      : "destructive"
                                  }
                                >
                                  {chunk.compliance}
                                </Badge>
                              </div>
                              {chunk.issues.length > 0 && (
                                <div className="space-y-2 mt-3">
                                  <div className="text-sm font-medium text-red-600">
                                    {chunk.issues.length} issue(s) found:
                                  </div>
                                  {chunk.issues.map((issue, issueIdx) => (
                                    <div
                                      key={issueIdx}
                                      className="bg-red-50 p-3 rounded text-sm space-y-1"
                                    >
                                      <div className="font-medium">
                                        Page {issue.page}: {issue.description}
                                      </div>
                                      <div className="text-gray-600">
                                        <span className="font-medium">
                                          Reference:
                                        </span>{" "}
                                        {issue.guideline_ref}
                                      </div>
                                      <div className="text-gray-600">
                                        {issue.reasoning}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
