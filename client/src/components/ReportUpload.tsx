import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { FileText } from "lucide-react";

interface ReportUploadProps {
  selectedGuidelinesCount: number;
  onStartMatch: (file: File) => Promise<void>;
}

export function ReportUpload({
  selectedGuidelinesCount,
  onStartMatch,
}: ReportUploadProps) {
  const [reportFile, setReportFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setReportFile(file);
    }
  };

  const handleSubmit = async () => {
    if (!reportFile) return;

    setIsSubmitting(true);
    try {
      await onStartMatch(reportFile);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
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
            <Label htmlFor="report-upload" className="cursor-pointer flex-1">
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
                onChange={handleFileSelect}
                className="hidden"
              />
            </Label>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="text-sm text-gray-600">
            {selectedGuidelinesCount > 0 ? (
              <span>{selectedGuidelinesCount} guideline(s) selected</span>
            ) : (
              <span className="text-orange-600">
                Please select guidelines
              </span>
            )}
          </div>
          <Button
            onClick={handleSubmit}
            disabled={
              !reportFile || selectedGuidelinesCount === 0 || isSubmitting
            }
            size="lg"
          >
            {isSubmitting ? "Starting..." : "Start Matching"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
