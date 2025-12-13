import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Checkbox } from "./ui/checkbox";
import { Trash2, Eye } from "lucide-react";
import type { Guideline } from "../lib/api";

interface GuidelineListProps {
  guidelines: Guideline[];
  selectedGuidelines: string[];
  onGuidelineUpload: (file: File) => Promise<void>;
  onGuidelineDelete: (id: string) => Promise<void>;
  onGuidelineToggle: (id: string) => void;
  onViewChecklist: (id: string) => void;
}

export function GuidelineList({
  guidelines,
  selectedGuidelines,
  // onGuidelineUpload,
  onGuidelineDelete,
  onGuidelineToggle,
  onViewChecklist,
}: GuidelineListProps) {
  // const [uploadingGuideline, setUploadingGuideline] = useState(false);
  // const [uploadProgress, setUploadProgress] = useState(0);

  // const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
  //   const file = e.target.files?.[0];
  //   if (!file) return;

  //   setUploadingGuideline(true);
  //   setUploadProgress(0);

  //   try {
  //     const progressInterval = setInterval(() => {
  //       setUploadProgress((prev) => Math.min(prev + 10, 90));
  //     }, 200);

  //     await onGuidelineUpload(file);

  //     clearInterval(progressInterval);
  //     setUploadProgress(100);

  //     e.target.value = "";
  //   } catch (err) {
  //     console.error("Upload error:", err);
  //   } finally {
  //     setUploadingGuideline(false);
  //     setTimeout(() => setUploadProgress(0), 1000);
  //   }
  // };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Guidelines</CardTitle>
        {/* <CardDescription>Manage compliance guidelines</CardDescription> */}
      </CardHeader>
      <CardContent className="">
        {/* <div>
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
                onChange={handleFileChange}
                disabled={uploadingGuideline}
                className="hidden"
              />
            </div>
          </Label>
          {uploadingGuideline && uploadProgress > 0 && (
            <Progress value={uploadProgress} className="mt-2" />
          )}
        </div> */}

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
                        checked={selectedGuidelines.includes(guideline.id)}
                        onCheckedChange={() => onGuidelineToggle(guideline.id)}
                      />
                      <div className="flex-1 min-w-0">
                        <label
                          htmlFor={guideline.id}
                          className="text-sm font-medium cursor-pointer block truncate"
                        >
                          {guideline.filename}
                        </label>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {guideline.pages && (
                            <Badge variant="secondary" className="text-xs">
                              {guideline.pages} requirements
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
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onViewChecklist(guideline.id)}
                        title="View checklist"
                      >
                        <Eye className="h-4 w-4 text-blue-500 mr-1" />
                        <span className="text-blue-500">View</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onGuidelineDelete(guideline.id)}
                        title="Delete guideline"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
