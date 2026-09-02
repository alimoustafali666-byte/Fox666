// Types mirror the backend's Pydantic response schemas field-for-field
// (see backend/app/modules/*/schemas.py) -- kept hand-written rather than
// generated, since the API surface for this MVP is small and stable.

export type Role = "owner" | "admin" | "manager" | "member";

export interface UserPublic {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface MeResponse {
  user: UserPublic;
  company_id: string;
  role: Role;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface CompanyPublic {
  id: string;
  name: string;
  timezone: string;
  country: string;
  has_logo: boolean;
}

export interface DailyBriefSchedule {
  enabled: boolean;
  time: string;
  timezone: string;
  last_scheduled_date: string | null;
}

export interface CurrentCompanyResponse {
  company: CompanyPublic;
  role: Role;
}

export interface CompanyMemberPublic {
  user_id: string;
  email: string;
  full_name: string | null;
  role: Role;
  created_at: string;
}

export interface CompanyMembershipPublic {
  company_id: string;
  company_name: string;
  role: Role;
}

export type InvitationStatus = "pending" | "accepted" | "expired" | "revoked";

export interface InvitationPublic {
  id: string;
  email: string;
  role: Role;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
}

export interface InvitationCreateResponse extends InvitationPublic {
  token: string;
}

// --- Projects ---

export const PROJECT_STATUSES = [
  "planning",
  "active",
  "on_hold",
  "completed",
  "cancelled",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export interface ProjectPublic {
  id: string;
  company_id: string;
  name: string;
  project_code: string | null;
  description: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectPage {
  items: ProjectPublic[];
  next_cursor: string | null;
}

// --- Documents ---

export const DOCUMENT_TYPES = [
  "contract",
  "boq",
  "quotation",
  "invoice",
  "purchase_order",
  "project_report",
  "other",
] as const;
export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export type DocumentStatus = "uploaded" | "processing" | "processed" | "failed";
export type DocumentIndexingStatus = "not_indexed" | "indexing" | "indexed" | "failed";

export interface DocumentPublic {
  id: string;
  company_id: string;
  project_id: string | null;
  uploaded_by: string;
  file_name: string;
  file_type: string;
  file_size_bytes: number;
  document_type: DocumentType;
  status: DocumentStatus;
  checksum_sha256: string;
  processing_error_code: string | null;
  processing_error_message: string | null;
  indexing_status: DocumentIndexingStatus;
  indexing_error_code: string | null;
  indexing_error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentPage {
  items: DocumentPublic[];
  next_cursor: string | null;
}

export interface DocumentDownloadResponse {
  download_url: string;
  expires_in_seconds: number;
}

// --- Conversations / Ask Your Business ---

export interface ConversationPublic {
  id: string;
  company_id: string;
  created_by: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationPage {
  items: ConversationPublic[];
  next_cursor: string | null;
}

export interface CitationPublic {
  document_chunk_id: string;
  document_id: string;
  file_name: string;
  document_type: DocumentType;
  project_id: string | null;
  page_number: number | null;
  sheet_name: string | null;
  section_name: string | null;
  source_location: Record<string, unknown> | null;
}

export interface MessagePublic {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  is_sufficient: boolean | null;
  model_identifier: string | null;
  created_at: string;
  citations: CitationPublic[];
}

export interface MessagePage {
  items: MessagePublic[];
  next_cursor: string | null;
}

// --- Daily Management Brief ---

export const BRIEF_ITEM_CATEGORIES = [
  "new_information",
  "pending_action",
  "follow_up",
  "potential_issue",
] as const;
export type BriefItemCategory = (typeof BRIEF_ITEM_CATEGORIES)[number];

export interface BriefItemPublic {
  id: string;
  category: BriefItemCategory;
  text: string;
  priority: number;
  source_document_id: string | null;
}

export interface DailyBriefPublic {
  id: string;
  company_id: string;
  generated_by: string;
  brief_date: string;
  summary: string;
  generated_at: string;
  items: BriefItemPublic[];
}

export interface DailyBriefSummary {
  id: string;
  company_id: string;
  generated_by: string;
  brief_date: string;
  summary: string;
  generated_at: string;
}

export interface DailyBriefPage {
  items: DailyBriefSummary[];
  next_cursor: string | null;
}

// --- Audit log ---

export interface AuditLogEntry {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  next_cursor: string | null;
}

// --- Help & Support (Step 17) ---

export const SUPPORT_TICKET_CATEGORIES = [
  "getting_started",
  "account_login",
  "projects",
  "documents",
  "upload_processing_indexing",
  "ask_your_business",
  "daily_brief",
  "language_settings",
  "roles_permissions",
  "troubleshooting",
  "other",
] as const;
export type SupportTicketCategory = (typeof SUPPORT_TICKET_CATEGORIES)[number];

export const SUPPORT_TICKET_PRIORITIES = ["low", "normal", "high", "urgent"] as const;
export type SupportTicketPriority = (typeof SUPPORT_TICKET_PRIORITIES)[number];

export const SUPPORT_TICKET_STATUSES = [
  "open",
  "in_progress",
  "waiting_for_user",
  "resolved",
  "closed",
] as const;
export type SupportTicketStatus = (typeof SUPPORT_TICKET_STATUSES)[number];

export interface SupportDiagnosticsInput {
  page?: string;
  document_id?: string;
  project_id?: string;
  user_agent_summary?: string;
  app_version?: string;
}

export interface SupportTicketPublic {
  id: string;
  company_id: string;
  created_by: string;
  category: SupportTicketCategory;
  subject: string;
  description: string;
  priority: SupportTicketPriority;
  status: SupportTicketStatus;
  reference_code: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface SupportTicketCommentPublic {
  id: string;
  ticket_id: string;
  author_type: "user" | "support";
  author_user_id: string | null;
  body: string;
  created_at: string;
}

export interface SupportTicketDetail extends SupportTicketPublic {
  comments: SupportTicketCommentPublic[];
}

export interface SupportTicketPage {
  items: SupportTicketPublic[];
  next_cursor: string | null;
}

export interface SupportArticlePublic {
  slug: string;
  category: SupportTicketCategory;
  title: string;
  body: string;
}

export interface SupportArticlePage {
  items: SupportArticlePublic[];
}

export interface SupportAssistantCitation {
  article_slug: string;
  title: string;
}

export interface SupportAssistantAskResponse {
  answer: string;
  sufficient: boolean;
  citations: SupportAssistantCitation[];
  used_diagnostics: boolean;
}

// --- Collaboration / Messages (Step 18) ---

export const CONVERSATION_TYPES = ["direct", "group", "project_channel"] as const;
export type ConversationType = (typeof CONVERSATION_TYPES)[number];

export const CONVERSATION_MEMBER_ROLES = ["owner", "admin", "member"] as const;
export type ConversationMemberRole = (typeof CONVERSATION_MEMBER_ROLES)[number];

export const NOTIFICATION_PREFS = ["all", "mentions", "muted"] as const;
export type NotificationPref = (typeof NOTIFICATION_PREFS)[number];

export const REACTION_EMOJIS = [
  "thumbsup",
  "thumbsdown",
  "heart",
  "laugh",
  "surprised",
  "sad",
  "pray",
  "party",
] as const;
export type ReactionEmoji = (typeof REACTION_EMOJIS)[number];

export interface ChatConversationPublic {
  id: string;
  company_id: string;
  type: ConversationType;
  name: string | null;
  description: string | null;
  project_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  unread_count: number;
}

export interface ChatConversationPage {
  items: ChatConversationPublic[];
  next_cursor: string | null;
}

export interface ConversationMemberPublic {
  user_id: string;
  full_name: string | null;
  role: ConversationMemberRole;
  notification_pref: NotificationPref;
  joined_at: string;
  last_read_at: string | null;
}

export const ATTACHMENT_KINDS = ["file", "image", "voice_note"] as const;
export type AttachmentKind = (typeof ATTACHMENT_KINDS)[number];

export interface AttachmentPublic {
  id: string;
  kind: AttachmentKind;
  file_name: string;
  file_type: string;
  file_size_bytes: number;
  duration_seconds: number | null;
  created_at: string;
}

export interface ReactionSummary {
  emoji: ReactionEmoji;
  user_ids: string[];
}

export interface ChatMessagePublic {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  sender_name: string | null;
  message_type: "text" | "system";
  content: string;
  reply_to_message_id: string | null;
  shared_document_id: string | null;
  edited_at: string | null;
  deleted_at: string | null;
  created_at: string;
  attachments: AttachmentPublic[];
  reactions: ReactionSummary[];
}

export interface ChatMessagePage {
  items: ChatMessagePublic[];
  next_cursor: string | null;
}

export interface PinnedMessagePublic {
  message_id: string;
  pinned_by: string;
  pinned_at: string;
}

export const COLLABORATION_NOTIFICATION_TYPES = [
  "new_message",
  "mention",
  "reply",
  "group_added",
  "group_removed",
  "project_channel_activity",
  "support_ticket_update",
  "task_assigned",
  "task_reassigned",
  "task_comment",
] as const;
export type CollaborationNotificationType = (typeof COLLABORATION_NOTIFICATION_TYPES)[number];

export interface CollaborationNotificationPublic {
  id: string;
  type: CollaborationNotificationType;
  conversation_id: string | null;
  message_id: string | null;
  support_ticket_id: string | null;
  task_id: string | null;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string;
}

export interface CollaborationNotificationPage {
  items: CollaborationNotificationPublic[];
  unread_count: number;
}

export const CALL_TYPES = ["voice", "video"] as const;
export type CallType = (typeof CALL_TYPES)[number];

export const CALL_STATUSES = ["ringing", "active", "ended", "missed", "declined"] as const;
export type CallStatus = (typeof CALL_STATUSES)[number];

export const CALL_PARTICIPANT_STATUSES = ["invited", "ringing", "joined", "declined", "missed", "left"] as const;
export type CallParticipantStatus = (typeof CALL_PARTICIPANT_STATUSES)[number];

export interface CallParticipantPublic {
  user_id: string;
  status: CallParticipantStatus;
  joined_at: string | null;
  left_at: string | null;
}

export interface CallSessionPublic {
  id: string;
  conversation_id: string;
  initiated_by: string;
  call_type: CallType;
  status: CallStatus;
  started_at: string;
  ended_at: string | null;
  ended_reason: string | null;
  participants: CallParticipantPublic[];
}

export interface AiDecisionPublic {
  description: string;
  confirmed: boolean;
  source_message_id: string | null;
}

export interface AiActionItemPublic {
  description: string;
  possible_assignee: string | null;
  due_date: string | null;
  source_message_id: string | null;
}

export interface AiInsightsResponse {
  summary: string;
  decisions: AiDecisionPublic[];
  action_items: AiActionItemPublic[];
}

export interface AiAnswerResponse {
  answer: string;
  sufficient: boolean;
  citations: { message_id: string }[];
}

// --- Tasks (Step 19) ---

export const TASK_STATUSES = ["todo", "in_progress", "blocked", "completed", "cancelled"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const TASK_PRIORITIES = ["low", "normal", "high", "urgent"] as const;
export type TaskPriority = (typeof TASK_PRIORITIES)[number];

export const TASK_SOURCE_TYPES = ["manual", "document", "message", "conversation", "daily_brief", "ai_suggestion"] as const;
export type TaskSourceType = (typeof TASK_SOURCE_TYPES)[number];

export const TASK_DUE_FILTERS = ["overdue", "due_today", "upcoming"] as const;
export type TaskDueFilter = (typeof TASK_DUE_FILTERS)[number];

export interface TaskPublic {
  id: string;
  company_id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assigned_to: string | null;
  assignee_name: string | null;
  created_by: string;
  creator_name: string | null;
  source_type: TaskSourceType;
  source_id: string | null;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskPage {
  items: TaskPublic[];
  next_cursor: string | null;
}

export interface TaskCommentPublic {
  id: string;
  task_id: string;
  author_user_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

export interface TaskActivityPublic {
  id: string;
  task_id: string;
  actor_user_id: string | null;
  actor_name: string | null;
  event_type: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
}

export interface TaskDashboardSummary {
  my_open_tasks: number;
  due_today: number;
  overdue: number;
  high_priority_open: number;
}

// --- Reports (Step 20) ---

export const REPORT_TYPES = [
  "projects", "documents", "tasks", "daily_brief", "audit_log", "support_tickets", "collaboration",
] as const;
export type ReportType = (typeof REPORT_TYPES)[number];

export const REPORT_EXPORT_FORMATS = ["csv", "xlsx", "docx", "pdf"] as const;
export type ReportExportFormat = (typeof REPORT_EXPORT_FORMATS)[number];

export interface ReportTypeInfo {
  type: ReportType;
  title_en: string;
  title_ar: string;
}

export interface ReportColumnPublic {
  key: string;
  label: string;
}

export interface ReportPreviewMeta {
  report_type: string;
  title: string;
  company_name: string;
  generated_at: string;
  generated_by: string;
  reference_number: string;
  filters_summary: string;
  row_count: number;
}

export interface ReportPreviewResponse {
  meta: ReportPreviewMeta;
  columns: ReportColumnPublic[];
  rows: Record<string, string>[];
}

export interface BriefSummary {
  brief_date: string;
  item_count: number;
  summary: string;
}

export interface RecentActivityEntry {
  created_at: string;
  actor: string;
  action: string;
  resource_type: string;
}

export interface DashboardSummaryResponse {
  project_status_counts: Record<string, number>;
  document_status_counts: Record<string, number>;
  my_tasks: TaskDashboardSummary;
  company_tasks: { open: number; overdue: number; blocked: number } | null;
  latest_brief: BriefSummary | null;
  my_ticket_status_counts: Record<string, number>;
  unread_notifications: number;
  recent_activity: RecentActivityEntry[] | null;
}

// --- Error envelope ---

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Array<{ loc: (string | number)[]; msg: string; type: string }>;
  };
}

