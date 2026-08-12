export type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  ui_language: string;
  profile?: {
    class_level: number;
    learning_streak: number;
    total_reading_seconds: number;
  } | null;
};

export type LessonCard = {
  id: string;
  title: string;
  language: string;
  content_type: string;
  subject?: string | null;
  class_level?: number | null;
  status: string;
  progress_percent: number;
  last_score?: number | null;
  last_studied_at?: string | null;
  page_count: number;
  word_count: number;
  summary?: string | null;
  is_demo?: boolean;
};

export type Word = { id: string; text: string; index: number; position: number };
export type Sentence = { id: string; text: string; position: number; words: Word[] };
export type Paragraph = { id: string; text: string; position: number; sentences: Sentence[] };
export type Section = {
  id: string;
  heading?: string | null;
  position: number;
  paragraphs: Paragraph[];
};

export type LessonContent = {
  lesson_id: string;
  title: string;
  language: string;
  content_type: string;
  summary?: string | null;
  sections: Section[];
};

export type StoryIllustration = {
  id: string;
  position: number;
  caption: string;
  storage_key: string;
  provider: string;
};

export type WordTiming = { word_id: string; start_ms: number; end_ms: number };

export type AudioAsset = {
  id: string;
  lesson_id: string;
  language: string;
  voice: string;
  speed: number;
  duration_ms: number;
  provider: string;
  timings: WordTiming[];
};

export type JobStatus = {
  id: string;
  lesson_id: string;
  status: string;
  current_step: string;
  progress_percent: number;
  message: string;
  error_message?: string | null;
};

export type UploadResponse = {
  lesson_id: string;
  job_id: string;
  status: string;
  message: string;
};

export type QuestionOption = { id: string; label: string; text: string; position: number };
export type Question = {
  id: string;
  question_type: string;
  prompt: string;
  position: number;
  points: number;
  options: QuestionOption[];
};

export type Quiz = {
  id: string;
  lesson_id: string;
  difficulty: string;
  class_level: number;
  language: string;
  question_count: number;
  status: string;
  questions: Question[];
};

export type AttemptResult = {
  id: string;
  quiz_id: string;
  score: number;
  max_score: number;
  accuracy: number;
  topics_understood: string[];
  needs_practice: string[];
  answers: {
    question_id: string;
    is_correct: boolean;
    score: number;
    feedback: string;
    expected_answer?: string | null;
    explanation?: string | null;
  }[];
  message: string;
};

export type Dashboard = {
  greeting: string;
  streak: number;
  average_score: number;
  reading_time_minutes: number;
  quiz_accuracy: number;
  recent_lessons: LessonCard[];
  continue_learning: LessonCard[];
  subjects: { name: string; count: number; avg_progress: number }[];
  completed_count: number;
};

export type ReadingMode = "listen" | "read" | "listen_read";
export type SpeedOption = "very_slow" | "slow" | "normal" | "fast";
/** natural = word highlight + pauses; word = karaoke; direct = fluent narration, no highlight */
export type PlaybackStyle = "natural" | "word" | "direct";
