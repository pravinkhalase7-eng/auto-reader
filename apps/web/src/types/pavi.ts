export type PaviConfirmation = {
  kind: string;
  title: string;
  when_label: string;
  phone_call_enabled: boolean;
  extra?: string | null;
};

export type ChatResponse = {
  conversation_id: string;
  message: string;
  role: string;
  confirmation?: PaviConfirmation | null;
};

export type PaviMessage = {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  message_type: string;
  created_at: string;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: PaviMessage[];
};

export type Reminder = {
  id: string;
  title: string;
  description?: string | null;
  reminder_time_utc: string;
  when_label: string;
  timezone: string;
  status: string;
  reminder_type: string;
  phone_call_enabled: boolean;
  phone_number_masked: string;
  recurrence_rule?: string | null;
  language: string;
  last_error?: string | null;
  created_at: string;
  completed_at?: string | null;
  cancelled_at?: string | null;
};

export type Appointment = {
  id: string;
  title: string;
  description?: string | null;
  appointment_time_utc: string;
  when_label: string;
  timezone: string;
  location?: string | null;
  booking_reference?: string | null;
  phone_call_enabled: boolean;
  status: string;
  language: string;
  created_at: string;
};

export type PhoneCall = {
  id: string;
  reminder_id?: string | null;
  twilio_call_sid?: string | null;
  phone_number_masked: string;
  status: string;
  started_at?: string | null;
  answered_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  error_message?: string | null;
  attempt_number: number;
  provider: string;
  created_at: string;
};

export type Preference = {
  phone_number?: string | null;
  phone_number_masked: string;
  phone_call_enabled: boolean;
  preferred_language: "en" | "hi" | "mr" | string;
  timezone: string;
};

export type ScheduleItem = {
  id: string;
  kind: string;
  title: string;
  when_utc: string;
  when_label: string;
  timezone: string;
  phone_call_enabled: boolean;
  status: string;
  location?: string | null;
};

export type UpcomingSchedule = {
  timezone: string;
  items: ScheduleItem[];
  today: ScheduleItem[];
  tomorrow: ScheduleItem[];
  later: ScheduleItem[];
};

export type PaviStats = {
  total_reminders: number;
  pending_reminders: number;
  completed_reminders: number;
  failed_reminders: number;
  calls_made: number;
  calls_answered: number;
  calls_failed: number;
};

export type ReminderCreateInput = {
  title: string;
  description?: string;
  reminder_time: string;
  timezone?: string;
  phone_call_enabled?: boolean;
  phone_number?: string;
  language?: string;
  recurrence_rule?: string;
  reminder_type?: string;
};
