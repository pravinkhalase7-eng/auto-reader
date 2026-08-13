import { api } from "@/lib/api";
import type {
  Appointment,
  ChatResponse,
  Conversation,
  PhoneCall,
  Preference,
  PaviStats,
  Reminder,
  ReminderCreateInput,
  UpcomingSchedule,
} from "@/types/pavi";

export function sendChatMessage(message: string, conversationId?: string | null) {
  return api<ChatResponse>("/pavi/chat", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId || undefined }),
  });
}

export function sendVoiceTranscript(transcript: string, conversationId?: string | null) {
  return api<ChatResponse>("/pavi/voice/transcript", {
    method: "POST",
    body: JSON.stringify({
      message: transcript,
      transcript,
      conversation_id: conversationId || undefined,
    }),
  });
}

export function getConversations() {
  return api<Conversation[]>("/pavi/conversations");
}

export function getConversation(id: string) {
  return api<Conversation>(`/pavi/conversations/${id}`);
}

export function createReminder(body: ReminderCreateInput) {
  return api<Reminder>("/reminders", { method: "POST", body: JSON.stringify(body) });
}

export function getReminders() {
  return api<Reminder[]>("/reminders");
}

export function getUpcomingReminders() {
  return api<Reminder[]>("/reminders/upcoming");
}

export function updateReminder(id: string, body: Partial<ReminderCreateInput> & { reminder_time?: string }) {
  return api<Reminder>(`/reminders/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function cancelReminder(id: string) {
  return api<Reminder>(`/reminders/${id}`, { method: "DELETE" });
}

export function getAppointments() {
  return api<Appointment[]>("/appointments");
}

export function createAppointment(body: {
  title: string;
  appointment_time: string;
  location?: string;
  reminder_offset_minutes?: number;
  phone_call_enabled?: boolean;
}) {
  return api<Appointment>("/appointments", { method: "POST", body: JSON.stringify(body) });
}

export function updateAppointment(id: string, body: Record<string, unknown>) {
  return api<Appointment>(`/appointments/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function cancelAppointment(id: string) {
  return api<Appointment>(`/appointments/${id}`, { method: "DELETE" });
}

export function getUpcomingSchedule() {
  return api<UpcomingSchedule>("/pavi/schedule");
}

export function getPhoneCallHistory() {
  return api<PhoneCall[]>("/voice/calls");
}

export function getPaviStats() {
  return api<PaviStats>("/pavi/stats");
}

export function getPreferences() {
  return api<Preference>("/pavi/preferences");
}

export function updatePreferences(body: Partial<Preference> & { phone_number?: string }) {
  return api<Preference>("/pavi/preferences", { method: "PATCH", body: JSON.stringify(body) });
}
