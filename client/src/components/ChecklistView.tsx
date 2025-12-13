import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { ArrowLeft, Loader2 } from "lucide-react";
import { api, type ChecklistDetails } from "../lib/api";

export function ChecklistView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [checklist, setChecklist] = useState<ChecklistDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchChecklist = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getChecklistDetails(id);
        setChecklist(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load checklist"
        );
      } finally {
        setLoading(false);
      }
    };

    fetchChecklist();
  }, [id]);

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
        return "bg-red-100 text-red-800 border-red-300";
      case "high":
        return "bg-orange-100 text-orange-800 border-orange-300";
      case "medium":
        return "bg-yellow-100 text-yellow-800 border-yellow-300";
      case "low":
        return "bg-blue-100 text-blue-800 border-blue-300";
      default:
        return "bg-gray-100 text-gray-800 border-gray-300";
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
      </div>
    );
  }

  if (error || !checklist) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-red-600">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-700">{error || "Checklist not found"}</p>
            <Button onClick={() => navigate("/")} className="mt-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Home
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6">
      <div className="max-w-full mx-auto space-y-6">
        <div className="flex flex-col items-start gap-2 md:flex-row md:items-center md:gap-4">
          {/* Back button sits at the top-left on mobile (stacked) and to the left on desktop */}
          <div className="w-full md:w-auto flex items-start md:items-center">
            <Button
              variant="outline"
              onClick={() => {
                if (
                  typeof window !== "undefined" &&
                  window.history.length > 1
                ) {
                  navigate(-1);
                } else {
                  navigate("/");
                }
              }}
              aria-label="Go back"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              <span>Back</span>
            </Button>
          </div>
          <div className="w-full md:flex-1">
            <h1 className="text-2xl md:text-3xl font-bold mt-2 md:mt-0">
              {checklist.checklist_name}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Version {checklist.version} • Last updated:{" "}
              {checklist.last_updated}
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Regulations Covered</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside space-y-1">
              {checklist.regulations.map((reg, idx) => (
                <li key={idx} className="text-sm text-gray-700">
                  {reg}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Requirements</CardTitle>
            <CardDescription>
              Total: {checklist.total_requirements} requirements
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="border mx-4 rounded-lg overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20 px-3">ID</TableHead>
                    <TableHead className="min-w-[300px] max-w-[400px] px-3">
                      Requirement
                    </TableHead>
                    <TableHead className="w-40 px-3">Category</TableHead>
                    <TableHead className="w-28 px-3">Severity</TableHead>
                    <TableHead className="min-w-[200px] px-3">
                      Search Keywords
                    </TableHead>

                  </TableRow>
                </TableHeader>
                <TableBody>
                  {checklist.requirements.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="font-mono text-sm px-3 align-top">
                        {req.id}
                      </TableCell>
                      <TableCell className="px-3 align-top">
                        <p className="text-sm whitespace-normal break-words">
                          {req.requirement}
                        </p>
                      </TableCell>
                      <TableCell className="px-3 align-top">
                        <span className="text-sm text-gray-700 whitespace-normal break-words">
                          {req.category}
                        </span>
                      </TableCell>
                      <TableCell className="px-3 align-top">
                        <Badge
                          variant="outline"
                          className={getSeverityColor(req.severity)}
                        >
                          {req.severity}
                        </Badge>
                      </TableCell>
                      <TableCell className="px-3 align-top">
                        <div className="flex flex-wrap gap-1">
                          {req.search_keywords.map((keyword, idx) => (
                            <Badge
                              key={idx}
                              variant="secondary"
                              className="text-xs"
                            >
                              {keyword}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>

                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
