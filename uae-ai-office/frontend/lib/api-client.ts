// Thin typed fetch wrapper over the backend's /v1 API.
//
// Token handling mirrors the backend contract exactly (see
// backend/app/modules/auth/router.py): the access token is returned in
// the JSON response body and is short-lived, so it is held here in
// memory only (never localStorage -- avoids leaving it readable to any
// script that can reach page storage). The refresh token lives in an
// httpOnly cookie scoped to /v1/auth that this client never reads
// directly; refreshing is just a POST with credentials included.
import type {
  AccessTokenResponse,
  AiAnswerResponse,
  AiInsightsResponse,
  ApiErrorBody,
  AttachmentPublic,
  AuditLogPage,
  CallParticipantPublic,
  CallParticipantStatus,
  CallSessionPublic,
  CallType,
  ChatConversationPage,
  ChatConversationPublic,
  ChatMessagePage,
  ChatMessagePublic,
  CitationPublic,
  CollaborationNotificationPage,
  CompanyPublic,
  DailyBriefSchedule,
  ConversationMemberPublic,
  ConversationPage,
  ConversationPublic,
  CurrentCompanyResponse,
  CompanyMemberPublic,
  DailyBriefPage,
  DailyBriefPublic,
  DashboardSummaryResponse,
  DocumentDownloadResponse,
  DocumentPage,
  DocumentPublic,
  DocumentType,
  MeResponse,
  CompanyMembershipPublic,
  InvitationCreateResponse,
  InvitationPublic,
  MessagePage,
  MessagePublic,
  NotificationPref,
  PinnedMessagePublic,
  ProjectPage,
  ProjectPublic,
  ProjectStatus,
  ReactionEmoji,
  ReportExportFormat,
  ReportPreviewResponse,
  ReportType,
  ReportTypeInfo,
  Role,
  SupportArticlePage,
  SupportArticlePublic,
  SupportAssistantAskResponse,
  SupportDiagnosticsInput,
  SupportTicketCategory,
  SupportTicketCommentPublic,
  SupportTicketDetail,
  SupportTicketPage,
  SupportTicketPriority,
  SupportTicketPublic,
  SupportTicketStatus,
  TaskActivityPublic,
  TaskCommentPublic,
  TaskDashboardSummary,
  TaskDueFilter,
  TaskPage,
  TaskPriority,
  TaskPublic,
  TaskSourceType,
  TaskStatus,
} from "./types";

function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) return process.env.NEXT_PUBLIC_API_BASE_URL;
  return "/v1";
}

const API_BASE_URL = getApiBaseUrl();

// The realtime WebSocket endpoint lives on the same origin/path prefix as
// the REST API (see backend/app/modules/collaboration/router.py's "/ws"
// route) -- only the scheme changes (http -> ws, https -> wss). The
// access token travels as a query parameter because the browser
// WebSocket API cannot set an Authorization header on the handshake.
export function buildCollaborationWebSocketUrl(token: string): string {
  const { protocol, host } = window.location;
  const wsProtocol = protocol === "https:" ? "wss" : "ws";
  return `${wsProtocol}://${host}/v1/collaboration/ws?token=${encodeURIComponent(token)}`;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: ApiErrorBody["error"]["details"];

  constructor(status: number, code: string, message: string, details?: ApiErrorBody["error"]["details"]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let accessToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// AuthProvider registers a callback here so that a definitive
// (post-refresh-attempt) 401 anywhere in the app can clear client state
// and redirect to /login, without every call site handling that itself.
export function registerUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn;
}

async function parseErrorBody(res: Response): Promise<ApiErrorBody["error"]> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (body?.error?.code && body?.error?.message) {
      return body.error;
    }
  } catch {
    // fall through to generic message below
  }
  return { code: "unknown_error", message: `Request failed with status ${res.status}.` };
}

let refreshInFlight: Promise<boolean> | null = null;

// The refresh token is single-use and rotates on every call (a fresh
// Set-Cookie comes back each time -- see backend/app/modules/auth/router.py).
// Two concurrent callers (e.g. React Strict Mode's double-invoked mount
// effect, or two components refreshing at once) must never both send the
// same cookie value: the second one arrives after the first has already
// rotated it away and gets a spurious 401. Collapsing concurrent calls
// into a single in-flight request is a correctness requirement here, not
// just a request-count optimization.
async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return false;
      const data = (await res.json()) as AccessTokenResponse;
      setAccessToken(data.access_token);
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  query?: Record<string, string | number | undefined | null>;
  skipAuthRetry?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function rawRequest(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const url = buildUrl(path, options.query);
  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body,
    credentials: "include",
  });
  if (path === "/auth/login") {
    void response
      .clone()
      .text()
      .then((responseBody) => {
        console.error("UAE AI Office login diagnostic", {
          url,
          method: options.method ?? "GET",
          status: response.status,
          responseBody,
        });
      })
      .catch((error: unknown) => {
        console.error("UAE AI Office login diagnostic network error", { url, error });
      });
  }
  return response;
}

async function requestResponse(path: string, options: RequestOptions = {}): Promise<Response> {
  let res = await rawRequest(path, options);

  if (res.status === 401 && !options.skipAuthRetry && path !== "/auth/refresh") {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      res = await rawRequest(path, options);
    } else {
      setAccessToken(null);
      unauthorizedHandler?.();
      const error = await parseErrorBody(res);
      throw new ApiError(res.status, error.code, error.message, error.details);
    }
  }

  if (res.status === 401) {
    setAccessToken(null);
    unauthorizedHandler?.();
  }

  if (!res.ok) {
    const error = await parseErrorBody(res);
    throw new ApiError(res.status, error.code, error.message, error.details);
  }

  return res;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await requestResponse(path, options);
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// For binary responses (company logo, generated report files) -- same
// auth/refresh/error handling as request(), but resolves to a Blob
// instead of parsing JSON. Callers turn the blob into an object URL
// (for an inline <img>) or trigger a save (for a report download).
async function requestBlob(path: string, options: RequestOptions = {}): Promise<{ blob: Blob; filename: string | null }> {
  const res = await requestResponse(path, options);
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]*)"/.exec(disposition);
  return { blob: await res.blob(), filename: match ? match[1] : null };
}

// --- Auth ---

export const authApi = {
  signup: (data: {
    email: string;
    password: string;
    full_name: string;
    company_name: string;
  }) => request<AccessTokenResponse>("/auth/signup", { method: "POST", body: data }),

  login: (data: { email: string; password: string }) =>
    request<AccessTokenResponse>("/auth/login", {
      method: "POST",
      body: { email: data.email, password: data.password },
    }),

  acceptInvitation: (token: string, data: { password: string; full_name: string }) =>
    request<AccessTokenResponse>(`/auth/invitations/${encodeURIComponent(token)}/accept`, { method: "POST", body: data }),

  refresh: () => refreshAccessToken(),

  logout: () =>
    request<void>("/auth/logout", { method: "POST", skipAuthRetry: true }).catch(() => undefined),

  me: () => request<MeResponse>("/auth/me"),
  updateProfile: (data: { full_name: string }) => request<MeResponse["user"]>("/auth/me", { method: "PATCH", body: data }),
  changePassword: (data: { current_password: string; new_password: string }) => request<void>("/auth/me/password", { method: "POST", body: data }),
  listCompanies: () => request<CompanyMembershipPublic[]>("/auth/me/companies"),
  switchCompany: (company_id: string) => request<AccessTokenResponse>("/auth/me/companies/switch", { method: "POST", body: { company_id } }),
};

// --- Tenancy ---

export const tenancyApi = {
  getCurrentCompany: () => request<CurrentCompanyResponse>("/companies/current"),
  listMembers: () => request<CompanyMemberPublic[]>("/companies/current/members"),

  updateCompany: (data: Partial<{ name: string; timezone: string; country: string }>) =>
    request<CurrentCompanyResponse>("/companies/current", { method: "PATCH", body: data }),

  uploadLogo: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<CompanyPublic>("/companies/current/logo", { method: "POST", formData });
  },

  deleteLogo: () => request<CompanyPublic>("/companies/current/logo", { method: "DELETE" }),

  getDailyBriefSchedule: () => request<DailyBriefSchedule>("/companies/current/daily-brief-schedule"),

  updateDailyBriefSchedule: (data: { enabled: boolean; time: string }) =>
    request<DailyBriefSchedule>("/companies/current/daily-brief-schedule", { method: "PATCH", body: data }),

  getLogoBlob: () => requestBlob("/companies/current/logo").then((r) => r.blob),

  updateMemberRole: (userId: string, role: Role) =>
    request<CompanyMemberPublic>(`/companies/current/members/${userId}`, { method: "PATCH", body: { role } }),

  removeMember: (userId: string) =>
    request<void>(`/companies/current/members/${userId}`, { method: "DELETE" }),

  listInvitations: () => request<InvitationPublic[]>("/companies/current/invitations"),

  createInvitation: (data: { email: string; role: Role }) =>
    request<InvitationCreateResponse>("/companies/current/invitations", { method: "POST", body: data }),

  resendInvitation: (invitationId: string) =>
    request<InvitationCreateResponse>(`/companies/current/invitations/${invitationId}/resend`, { method: "POST" }),

  cancelInvitation: (invitationId: string) =>
    request<void>(`/companies/current/invitations/${invitationId}`, { method: "DELETE" }),
};

// --- Projects ---

export const projectsApi = {
  list: (query?: { status?: string; name?: string; limit?: number; cursor?: string }) =>
    request<ProjectPage>("/projects", { query }),

  create: (data: { name: string; project_code?: string; description?: string; status?: ProjectStatus }) =>
    request<ProjectPublic>("/projects", { method: "POST", body: data }),

  get: (id: string) => request<ProjectPublic>(`/projects/${id}`),

  update: (
    id: string,
    data: Partial<{ name: string; project_code: string | null; description: string | null; status: ProjectStatus }>
  ) => request<ProjectPublic>(`/projects/${id}`, { method: "PATCH", body: data }),

  remove: (id: string) => request<ProjectPublic>(`/projects/${id}`, { method: "DELETE" }),
};

// --- Documents ---

export const documentsApi = {
  list: (query?: {
    project_id?: string;
    document_type?: string;
    status?: string;
    filename?: string;
    limit?: number;
    cursor?: string;
  }) => request<DocumentPage>("/documents", { query }),

  get: (id: string) => request<DocumentPublic>(`/documents/${id}`),

  upload: (data: { file: File; document_type: DocumentType; project_id?: string }) => {
    const formData = new FormData();
    formData.append("file", data.file);
    formData.append("document_type", data.document_type);
    if (data.project_id) formData.append("project_id", data.project_id);
    return request<DocumentPublic>("/documents", { method: "POST", formData });
  },

  process: (id: string) => request<DocumentPublic>(`/documents/${id}/process`, { method: "POST" }),

  index: (id: string) => request<DocumentPublic>(`/documents/${id}/index`, { method: "POST" }),

  remove: (id: string) => request<DocumentPublic>(`/documents/${id}`, { method: "DELETE" }),

  getDownloadUrl: (id: string) =>
    request<DocumentDownloadResponse>(`/documents/${id}/download`),
};

// --- Conversations / Ask Your Business ---

export const conversationsApi = {
  list: (query?: { limit?: number; cursor?: string }) =>
    request<ConversationPage>("/conversations", { query }),

  create: (data?: { title?: string }) =>
    request<ConversationPublic>("/conversations", { method: "POST", body: data ?? {} }),

  get: (id: string) => request<ConversationPublic>(`/conversations/${id}`),

  listMessages: (id: string, query?: { limit?: number; cursor?: string }) =>
    request<MessagePage>(`/conversations/${id}/messages`, { query }),

  ask: (id: string, question: string) =>
    request<MessagePublic>(`/conversations/${id}/messages`, {
      method: "POST",
      body: { question },
    }),
};

export type { CitationPublic };

// --- Daily Management Brief ---

export const briefsApi = {
  regenerate: () => request<DailyBriefPublic>("/briefs/regenerate", { method: "POST" }),
  getLatest: () => request<DailyBriefPublic>("/briefs/latest"),
  getByDate: (date: string) => request<DailyBriefPublic>(`/briefs/${date}`),
  list: (query?: { limit?: number; cursor?: string }) => request<DailyBriefPage>("/briefs", { query }),
};

// --- Audit log ---

export const auditApi = {
  list: (query?: {
    action?: string;
    resource_type?: string;
    limit?: number;
    cursor?: string;
  }) => request<AuditLogPage>("/audit-logs", { query }),
};

// --- Help & Support (Step 17) ---

export const supportApi = {
  listArticles: (query?: { category?: string; locale?: string }) =>
    request<SupportArticlePage>("/support/articles", { query }),

  getArticle: (slug: string, locale?: string) =>
    request<SupportArticlePublic>(`/support/articles/${slug}`, { query: { locale } }),

  searchArticles: (query: string, locale?: string) =>
    request<SupportArticlePage>("/support/search", { method: "POST", body: { query }, query: { locale } }),

  askAssistant: (
    question: string,
    diagnostics?: SupportDiagnosticsInput,
    locale?: string
  ) =>
    request<SupportAssistantAskResponse>("/support/assistant/ask", {
      method: "POST",
      body: { question, diagnostics },
      query: { locale },
    }),

  listTickets: (query?: { status?: string; limit?: number; cursor?: string }) =>
    request<SupportTicketPage>("/support/tickets", { query }),

  createTicket: (data: {
    category: SupportTicketCategory;
    subject: string;
    description: string;
    priority?: SupportTicketPriority;
    diagnostics?: SupportDiagnosticsInput;
  }) => request<SupportTicketPublic>("/support/tickets", { method: "POST", body: data }),

  getTicket: (id: string) => request<SupportTicketDetail>(`/support/tickets/${id}`),

  addComment: (id: string, body: string) =>
    request<SupportTicketCommentPublic>(`/support/tickets/${id}/comments`, {
      method: "POST",
      body: { body },
    }),

  updateTicketStatus: (id: string, status: SupportTicketStatus) =>
    request<SupportTicketPublic>(`/support/tickets/${id}/status`, {
      method: "PATCH",
      body: { status },
    }),
};

// --- Collaboration / Messages (Step 18) ---

export const collaborationApi = {
  createDirect: (other_user_id: string) =>
    request<ChatConversationPublic>("/collaboration/conversations/direct", {
      method: "POST",
      body: { other_user_id },
    }),

  createGroup: (data: { name: string; description?: string | null; member_user_ids: string[] }) =>
    request<ChatConversationPublic>("/collaboration/conversations/group", { method: "POST", body: data }),

  createProjectChannel: (data: {
    project_id: string;
    name: string;
    description?: string | null;
    member_user_ids: string[];
  }) => request<ChatConversationPublic>("/collaboration/conversations/project-channel", { method: "POST", body: data }),

  list: (query?: { limit?: number; cursor?: string }) =>
    request<ChatConversationPage>("/collaboration/conversations", { query }),

  get: (id: string) => request<ChatConversationPublic>(`/collaboration/conversations/${id}`),

  rename: (id: string, data: { name?: string | null; description?: string | null }) =>
    request<ChatConversationPublic>(`/collaboration/conversations/${id}`, { method: "PATCH", body: data }),

  listMembers: (id: string) => request<ConversationMemberPublic[]>(`/collaboration/conversations/${id}/members`),

  addMember: (id: string, user_id: string) =>
    request<ConversationMemberPublic>(`/collaboration/conversations/${id}/members`, {
      method: "POST",
      body: { user_id },
    }),

  removeMember: (id: string, userId: string) =>
    request<void>(`/collaboration/conversations/${id}/members/${userId}`, { method: "DELETE" }),

  leave: (id: string) => request<void>(`/collaboration/conversations/${id}/leave`, { method: "POST" }),

  updateNotificationPref: (id: string, pref: NotificationPref) =>
    request<ConversationMemberPublic>(`/collaboration/conversations/${id}/notification-pref`, {
      method: "PUT",
      body: { pref },
    }),

  markRead: (id: string, message_id?: string | null) =>
    request<void>(`/collaboration/conversations/${id}/read`, { method: "POST", body: { message_id } }),

  listMessages: (id: string, query?: { limit?: number; cursor?: string }) =>
    request<ChatMessagePage>(`/collaboration/conversations/${id}/messages`, { query }),

  sendMessage: (
    id: string,
    data: { content: string; reply_to_message_id?: string | null; shared_document_id?: string | null }
  ) => request<ChatMessagePublic>(`/collaboration/conversations/${id}/messages`, { method: "POST", body: data }),

  editMessage: (messageId: string, content: string) =>
    request<ChatMessagePublic>(`/collaboration/messages/${messageId}`, { method: "PATCH", body: { content } }),

  deleteMessage: (messageId: string) =>
    request<ChatMessagePublic>(`/collaboration/messages/${messageId}`, { method: "DELETE" }),

  getMessageLocation: (messageId: string) =>
    request<{ conversation_id: string }>(`/collaboration/messages/${messageId}/location`),

  searchConversation: (id: string, query: string) =>
    request<ChatMessagePage>(`/collaboration/conversations/${id}/search`, { method: "POST", body: { query } }),

  addReaction: (messageId: string, emoji: ReactionEmoji) =>
    request<void>(`/collaboration/messages/${messageId}/reactions`, { method: "POST", body: { emoji } }),

  removeReaction: (messageId: string, emoji: ReactionEmoji) =>
    request<void>(`/collaboration/messages/${messageId}/reactions/${emoji}`, { method: "DELETE" }),

  pinMessage: (conversationId: string, messageId: string) =>
    request<void>(`/collaboration/conversations/${conversationId}/pins/${messageId}`, { method: "POST" }),

  unpinMessage: (conversationId: string, messageId: string) =>
    request<void>(`/collaboration/conversations/${conversationId}/pins/${messageId}`, { method: "DELETE" }),

  listPins: (conversationId: string) =>
    request<PinnedMessagePublic[]>(`/collaboration/conversations/${conversationId}/pins`),

  uploadAttachment: (
    messageId: string,
    data: { conversation_id: string; file: File; duration_seconds?: number }
  ) => {
    const formData = new FormData();
    formData.append("conversation_id", data.conversation_id);
    formData.append("file", data.file);
    if (data.duration_seconds !== undefined) formData.append("duration_seconds", String(data.duration_seconds));
    return request<AttachmentPublic>(`/collaboration/messages/${messageId}/attachments`, { method: "POST", formData });
  },

  getAttachmentDownloadUrl: (attachmentId: string) =>
    request<{ url: string }>(`/collaboration/attachments/${attachmentId}/download-url`),

  listConversationMedia: (conversationId: string, query?: { kind?: string; limit?: number }) =>
    request<AttachmentPublic[]>(`/collaboration/conversations/${conversationId}/media`, { query }),

  listNotifications: (query?: { unread_only?: boolean; limit?: number }) =>
    request<CollaborationNotificationPage>("/collaboration/notifications", {
      query: query ? { unread_only: query.unread_only ? "true" : undefined, limit: query.limit } : undefined,
    }),

  markNotificationRead: (id: string) => request<void>(`/collaboration/notifications/${id}/read`, { method: "POST" }),

  markAllNotificationsRead: () => request<void>("/collaboration/notifications/read-all", { method: "POST" }),

  startCall: (conversationId: string, call_type: CallType) =>
    request<CallSessionPublic>(`/collaboration/conversations/${conversationId}/calls`, {
      method: "POST",
      body: { call_type },
    }),

  getCallSession: (callSessionId: string) => request<CallSessionPublic>(`/collaboration/calls/${callSessionId}`),

  respondToCall: (callSessionId: string, status: CallParticipantStatus) =>
    request<CallSessionPublic>(`/collaboration/calls/${callSessionId}/respond`, { method: "POST", body: { status } }),

  endCall: (callSessionId: string) =>
    request<CallSessionPublic>(`/collaboration/calls/${callSessionId}/end`, { method: "POST" }),

  listCallParticipants: (callSessionId: string) =>
    request<CallParticipantPublic[]>(`/collaboration/calls/${callSessionId}/participants`),

  aiSummarize: (conversationId: string) =>
    request<AiInsightsResponse>(`/collaboration/conversations/${conversationId}/ai/summarize`, { method: "POST" }),

  aiSummarizeUnread: (conversationId: string) =>
    request<AiInsightsResponse>(`/collaboration/conversations/${conversationId}/ai/summarize-unread`, { method: "POST" }),

  aiExtractDecisions: (conversationId: string) =>
    request<AiInsightsResponse>(`/collaboration/conversations/${conversationId}/ai/decisions`, { method: "POST" }),

  aiExtractActionItems: (conversationId: string) =>
    request<AiInsightsResponse>(`/collaboration/conversations/${conversationId}/ai/action-items`, { method: "POST" }),

  aiAsk: (conversationId: string, question: string) =>
    request<AiAnswerResponse>(`/collaboration/conversations/${conversationId}/ai/ask`, {
      method: "POST",
      body: { question },
    }),
};

// --- Tasks (Step 19) ---

export const tasksApi = {
  create: (data: {
    title: string;
    description?: string | null;
    project_id?: string | null;
    assigned_to?: string | null;
    priority?: TaskPriority;
    due_date?: string | null;
    source_type?: TaskSourceType;
    source_id?: string | null;
  }) => request<TaskPublic>("/tasks", { method: "POST", body: data }),

  list: (query?: {
    assigned_to?: string;
    created_by?: string;
    project_id?: string;
    unscoped_only?: boolean;
    status?: TaskStatus;
    open_only?: boolean;
    priority?: TaskPriority;
    due_filter?: TaskDueFilter;
    search?: string;
    cursor?: string;
    limit?: number;
  }) =>
    request<TaskPage>("/tasks", {
      query: query
        ? {
            ...query,
            unscoped_only: query.unscoped_only ? "true" : undefined,
            open_only: query.open_only ? "true" : undefined,
          }
        : undefined,
    }),

  summary: () => request<TaskDashboardSummary>("/tasks/summary"),

  get: (id: string) => request<TaskPublic>(`/tasks/${id}`),

  update: (
    id: string,
    data: Partial<{
      title: string;
      description: string | null;
      status: TaskStatus;
      priority: TaskPriority;
      assigned_to: string | null;
      project_id: string | null;
      due_date: string | null;
    }>
  ) => request<TaskPublic>(`/tasks/${id}`, { method: "PATCH", body: data }),

  listComments: (id: string) => request<TaskCommentPublic[]>(`/tasks/${id}/comments`),

  addComment: (id: string, body: string) =>
    request<TaskCommentPublic>(`/tasks/${id}/comments`, { method: "POST", body: { body } }),

  listActivity: (id: string) => request<TaskActivityPublic[]>(`/tasks/${id}/activity`),
};

// --- Reports (Step 20) ---

export interface ReportFilters {
  [key: string]: string | undefined;
  locale?: string;
  status?: string;
  priority?: string;
  project_id?: string;
  document_type?: string;
  due_filter?: string;
  search?: string;
  date?: string;
  date_from?: string;
  date_to?: string;
  action?: string;
  resource_type?: string;
  assigned_to?: string;
}

export const reportsApi = {
  listTypes: () => request<ReportTypeInfo[]>("/reports/types"),

  preview: (reportType: ReportType, filters?: ReportFilters) =>
    request<ReportPreviewResponse>(`/reports/${reportType}/preview`, { query: filters }),

  download: (reportType: ReportType, format: ReportExportFormat, filters?: ReportFilters) =>
    requestBlob(`/reports/${reportType}`, { query: { ...filters, format } }),

  dashboardSummary: () => request<DashboardSummaryResponse>("/reports/dashboard-summary"),
};

