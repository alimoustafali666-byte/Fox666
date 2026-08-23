from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "UAE AI Office API"
    log_level: str = "info"
    frontend_origin: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://uae_app:uae_app@localhost:5432/uae_ai_office"

    # No default: an accidentally-deployed default signing secret is a
    # real vulnerability, so startup must fail loudly if this isn't set
    # rather than silently falling back to something guessable.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14

    refresh_cookie_name: str = "refresh_token"
    # Must stay True in production -- a non-Secure cookie is sent over
    # plain HTTP, exposing the refresh token to network eavesdroppers.
    # Only override to False for local HTTP development.
    cookie_secure: bool = True

    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 900

    # 0 (default): never trust X-Forwarded-For, always use the direct TCP
    # peer address -- correct and safe for local dev and for "no reverse
    # proxy" deployments, since a client can set that header to anything.
    # >0: the app is known to sit behind exactly this many trusted
    # reverse-proxy hops, each of which appends its own entry to
    # X-Forwarded-For; the real client is then the Nth-from-the-right
    # entry (NOT the first, which an attacker in front of the first
    # trusted hop could have forged).
    trusted_proxy_hops: int = 0

    # "s3" for any real S3-compatible backend (AWS, MinIO, etc.) or
    # "fake" for an in-memory provider -- see app/core/storage/factory.py.
    # Defaults to "s3" for production-realistic behavior, but nothing at
    # app-boot time actually constructs a provider (unlike jwt_secret_key,
    # which Settings() itself requires), so the test suite and unrelated
    # local dev work never need real credentials just to start the app.
    # Required s3 fields are validated -- and made to fail clearly, not
    # via a confusing SDK error -- only when the provider is actually
    # requested.
    storage_provider: str = "s3"
    storage_endpoint_url: str | None = None
    storage_region: str = "me-central-1"
    storage_bucket: str | None = None
    storage_access_key_id: str | None = None
    storage_secret_access_key: str | None = None
    storage_use_ssl: bool = True

    # Default signed download URL lifetime (5 minutes, per the approved
    # design) and the hard ceiling no request -- however configured -- may
    # exceed.
    storage_signed_url_ttl_seconds: int = 300
    storage_max_signed_url_ttl_seconds: int = 3600

    # Not enforced by this step (no upload endpoint exists yet) -- carried
    # here so Step 8's Documents API reads the same approved limit from
    # one place rather than a second hard-coded constant.
    storage_max_upload_bytes: int = 25 * 1024 * 1024

    # Document processing (Step 9) resource limits -- explicit and
    # configuration-driven, per the approved design, protecting against
    # pathological input (an enormous page/sheet count, a spreadsheet
    # with absurd dimensions, a zip-bomb-shaped Office document part, or
    # simply an unreasonable amount of extracted text) rather than
    # assuming the 25MB upload cap alone bounds processing cost.
    processing_max_pdf_pages: int = 500
    processing_max_xlsx_sheets: int = 50
    processing_max_xlsx_rows_per_sheet: int = 50_000
    processing_max_xlsx_columns_per_sheet: int = 500
    processing_max_extracted_text_chars: int = 5_000_000
    # DOCX/XLSX are zip archives; python-docx/openpyxl decompress their
    # internal XML parts without a built-in size cap, so every zip entry
    # is checked against these before either library ever touches the
    # file (see app.modules.documents.processing.zip_safety).
    processing_max_zip_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    processing_max_zip_total_uncompressed_bytes: int = 150 * 1024 * 1024

    # Chunking targets (informational token counts -- see
    # app.modules.documents.processing.tokenizer for the counting
    # approximation used). Approved range is ~500-800 tokens with
    # ~10-15% overlap; these are the single configured point in that
    # range/ratio.
    processing_chunk_target_tokens: int = 650
    processing_chunk_overlap_ratio: float = 0.125

    # Embeddings + retrieval (Step 10). "voyage" for the real provider
    # (app.core.embeddings.voyage_provider) or "fake" for the
    # deterministic, network-free provider the test suite uses -- see
    # app.core.embeddings.factory. Defaults to "voyage" for
    # production-realistic behavior; like storage_provider, nothing at
    # app-boot time actually constructs one, so unrelated work never
    # needs a real API key just to start the app.
    embedding_provider: str = "voyage"
    embedding_api_key: str | None = None
    embedding_model: str = "voyage-3"
    # Must match app.modules.documents.models.EMBEDDING_VECTOR_DIMENSION
    # (the fixed pgvector column width) -- the factory refuses to build
    # a provider whose dimension disagrees with it. voyage-3's native
    # output dimension.
    embedding_dimension: int = 1024
    # Bounded batches: never send an entire (potentially large) document's
    # chunks to the provider in one request.
    embedding_batch_size: int = 32

    retrieval_top_k_default: int = 12
    retrieval_top_k_max: int = 20
    # Cosine similarity (1 - pgvector cosine_distance), since Voyage's
    # embeddings are the selected default and are designed for cosine
    # comparison. A conservative starting point, NOT calibrated against
    # real pilot data yet -- revisit once there's a real corpus and real
    # queries to tune against; too low lets irrelevant chunks through,
    # too high starves genuinely relevant results.
    retrieval_similarity_threshold: float = 0.3

    # Ask Your Business (Step 11). "anthropic" for the real provider
    # (app.core.llm.anthropic_provider) or "fake" for the deterministic,
    # network-free provider the test suite uses -- see app.core.llm.factory.
    # Defaults to "anthropic" for production-realistic behavior; nothing at
    # app-boot time constructs a provider, so unrelated work never needs a
    # real API key just to start the app.
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    # Sonnet-tier, per the approved Step 11 spec ("use a current Sonnet-tier
    # Claude model"). Configurable, not hard-coded elsewhere -- see the
    # Step 11 report for the disclosure that this exact identifier has not
    # been verified against a live API call in this environment (same
    # caveat as EMBEDDING_MODEL/voyage-3 in Step 10).
    claude_model: str = "claude-sonnet-5"
    # A short grounded Q&A answer plus a handful of citations never needs
    # anywhere near the SDK's own general-purpose default -- kept small and
    # explicit as a cost-control measure (see the Step 11 report).
    claude_max_output_tokens: int = 1024
    claude_timeout_seconds: float = 30.0
    # Passed to the Anthropic SDK client's own max_retries (connection
    # errors/408/409/429/>=500) -- bounded, not unbounded, per the Step 11
    # cost-control requirement.
    claude_max_retries: int = 2

    ask_max_question_length: int = 2000
    # How many of the most recent prior conversation turns (user+assistant
    # pairs) are passed to Claude as plain conversational context -- for
    # linguistic follow-up resolution only, never as a factual source (see
    # the Step 11 report's conversation-memory section). Small and fixed,
    # not the full conversation history.
    ask_max_history_turns: int = 2
    # At most one controlled corrective retry when Claude's structured
    # output is malformed or its citations fail validation -- never a loop.
    ask_max_citation_retries: int = 1

    # Daily Management Brief (Step 12, on-demand only -- no scheduler/cron/
    # background worker in this step). Reuses the same LLMProvider
    # abstraction and grounding discipline as Ask Your Business.
    # Incremental by design: only documents created/updated since the
    # company's last brief are ever considered, bounded further by these
    # two caps so a company with a large backlog can't produce an
    # unbounded prompt.
    brief_max_documents_per_run: int = 20
    brief_max_chars_per_document: int = 3000
    # "previous 1-3 briefs" per the approved architecture -- carried-
    # forward items are context for Claude to judge still-open vs.
    # resolved, never assumed still valid.
    brief_lookback_briefs: int = 3
    brief_max_carry_forward_items: int = 20
    # Passed per-call as `max_tokens` -- brief generation reuses the same
    # configured Anthropic client (and therefore the same
    # claude_timeout_seconds/claude_max_retries) as Ask Your Business;
    # only the output-token budget differs, since a brief can legitimately
    # contain more items than a single Q&A answer.
    brief_max_output_tokens: int = 2048
    # At most one controlled corrective retry when Claude's structured
    # output is malformed or an item's citation fails validation -- never
    # a loop, same bounded-retry discipline as Step 11's Ask Your Business.
    brief_max_citation_retries: int = 1

    # Support Center (Step 17). Support Assistant reuses the same
    # LLMProvider abstraction/grounding discipline as Ask Your Business
    # and the Daily Brief, but is architecturally isolated from both --
    # see app.modules.support.assistant_service's module docstring.
    support_kb_query_max_length: int = 300
    support_kb_top_k: int = 3
    support_assistant_question_max_length: int = 1000
    support_ticket_subject_max_length: int = 200
    support_ticket_description_max_length: int = 5000
    support_ticket_comment_max_length: int = 5000
    # Fixed-window in-process limiters (see app.modules.auth.rate_limit's
    # documented single-instance limitation -- the same tradeoff applies
    # here, unchanged, rather than introducing Redis for this step alone).
    support_ticket_create_rate_limit_max: int = 10
    support_ticket_create_rate_limit_window_seconds: int = 3600
    support_assistant_rate_limit_max: int = 30
    support_assistant_rate_limit_window_seconds: int = 3600

    # Collaboration / Messages (Step 18). Bounds documented as the
    # single-instance in-process limits they are -- see
    # app.modules.auth.rate_limit's module docstring for the same
    # documented production tradeoff, unchanged here rather than
    # introducing Redis for this step alone.
    collaboration_message_max_length: int = 8000
    collaboration_message_rate_limit_max: int = 60
    collaboration_message_rate_limit_window_seconds: int = 60
    collaboration_group_max_members: int = 200
    collaboration_search_query_max_length: int = 200
    collaboration_search_max_results: int = 50
    collaboration_attachment_max_size_bytes: int = 25 * 1024 * 1024
    collaboration_voice_note_max_seconds: int = 300
    collaboration_notification_list_max: int = 100
    # Bounded context window handed to the LLM for summaries/decisions/
    # action-items/Q&A -- never the full conversation history, same
    # "bounded, already-authorized context" discipline as Ask Your
    # Business's document_context and the Daily Brief's new_documents.
    collaboration_insights_max_messages: int = 200
    collaboration_insights_max_output_tokens: int = 2048
    collaboration_ai_rate_limit_max: int = 20
    collaboration_ai_rate_limit_window_seconds: int = 3600


settings = Settings()

