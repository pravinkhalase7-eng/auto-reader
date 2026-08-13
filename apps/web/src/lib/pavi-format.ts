export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "Pending",
    scheduled: "Scheduled",
    processing: "Calling…",
    completed: "Completed",
    cancelled: "Cancelled",
    failed: "Failed",
    queued: "Queued",
    ringing: "Ringing",
    "in-progress": "In progress",
    busy: "Busy",
    "no-answer": "No answer",
  };
  return map[status] || status;
}

export function isFailedStatus(status: string): boolean {
  return ["failed", "busy", "no-answer", "canceled", "cancelled"].includes(status);
}
