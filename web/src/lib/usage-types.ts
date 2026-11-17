export type Usage = {
  documents: number;
  chunks: number;
  characters: number;
  collections: number;
  conversations: number;
  questions: number;
  answers: number;
  refused_answers: number;
  feedback_up: number;
  feedback_down: number;
  imports: { succeeded: number; failed: number; active: number };
  daily_questions: { date: string; count: number }[];
  limits: {
    questions_per_minute: number;
    max_upload_mb: number;
    max_document_chars: number;
    max_active_imports: number;
  };
};
