import { Badge } from "./ui/badge";
import type { ComplianceRow } from "../lib/api";

interface ComplianceTableProps {
  rows: ComplianceRow[];
  isProcessing: boolean;
}

export function ComplianceTable({ rows, isProcessing }: ComplianceTableProps) {
  return (
    <div className="space-y-3">
      <h3 className="font-semibold">
        Compliance Report
        {isProcessing && (
          <span className="text-sm text-gray-500 ml-2">(Live updates...)</span>
        )}
      </h3>
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-700 border-b">
                  Requirement ID / Reference
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-700 border-b">
                  Requirement Text / IHM Output / Evidence
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-700 border-b">
                  Status
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-700 border-b">
                  Remarks
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.length > 0 ? (
                rows.map((row, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900">
                      <div className="space-y-1">
                        <div className="font-medium">
                          {row.requirement_id || row.mepc_reference}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {row.requirement_text || row.ihm_output || row.evidence}
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={
                          row.status === "Compliant"
                            ? "default"
                            : row.status === "Non-Compliant"
                            ? "destructive"
                            : "secondary"
                        }
                        className={
                          row.status === "Partially Compliant"
                            ? "bg-orange-100 text-orange-800 border-orange-300"
                            : row.status === "Compliant"
                            ? "bg-green-100 text-green-800 border-green-300"
                            : ""
                        }
                      >
                        {row.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{row.remarks}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    {isProcessing
                      ? "Processing... Results will appear here as they're generated."
                      : "No results yet."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
