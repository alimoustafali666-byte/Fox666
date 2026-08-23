"""The Step 17 knowledge-base foundation. Deliberately code-backed rather
than a database table with an admin editor: an MVP-appropriate,
version-controlled, reviewable source of truth for a first release. Each
Article's shape (slug/category/title/body per locale/keywords) maps
directly onto what a future `support_articles` table + CMS/admin editor
would need -- swapping this list for a repository-backed equivalent
would not require changing anything that reads it (app.modules.support.
kb_search, app.modules.support.assistant_service), only how ARTICLES is
populated.

Every article describes real, already-implemented product behavior
(Steps 1-16) -- nothing here promises a feature that doesn't exist.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Article:
    slug: str
    category: str
    title_en: str
    title_ar: str
    body_en: str
    body_ar: str
    keywords_en: tuple[str, ...] = field(default_factory=tuple)
    keywords_ar: tuple[str, ...] = field(default_factory=tuple)


ARTICLES: tuple[Article, ...] = (
    Article(
        slug="getting-started-overview",
        category="getting_started",
        title_en="Getting started with UAE AI Office",
        title_ar="البدء في استخدام UAE AI Office",
        body_en=(
            "UAE AI Office helps your team get grounded answers from your own contracts, BOQs, "
            "invoices, and reports. The typical flow is: create a project (optional), upload a "
            "document, process and index it, then ask questions about it in Ask Your Business or "
            "read a summary in the Daily Management Brief. Every answer cites the exact document "
            "and location it came from."
        ),
        body_ar=(
            "يساعد UAE AI Office فريقك على الحصول على إجابات مستندة إلى عقودك وجداول الكميات "
            "والفواتير والتقارير الخاصة بك. المسار المعتاد هو: إنشاء مشروع (اختياري)، رفع مستند، "
            "معالجته وفهرسته، ثم طرح الأسئلة عنه في اسأل عن أعمالك أو قراءة ملخص في الموجز الإداري "
            "اليومي. كل إجابة تذكر المستند والموقع الدقيق الذي استُمدت منه."
        ),
        keywords_en=("start", "overview", "welcome", "how it works", "flow"),
        keywords_ar=("بدء", "نظرة عامة", "كيف يعمل", "مرحبا"),
    ),
    Article(
        slug="account-login-basics",
        category="account_login",
        title_en="Signing up, signing in, and your session",
        title_ar="إنشاء حساب وتسجيل الدخول والجلسة",
        body_en=(
            "Creating a workspace makes you the Owner of a new company. Sign in with your work "
            "email and password. Your session refreshes automatically while you use the app; if "
            "it expires you'll be asked to sign in again. Passwords must be at least 12 characters."
        ),
        body_ar=(
            "إنشاء مساحة عمل يجعلك مالك شركة جديدة. سجّل الدخول ببريدك الإلكتروني للعمل وكلمة "
            "المرور. تتجدد جلستك تلقائيًا أثناء استخدام التطبيق؛ وإذا انتهت صلاحيتها سيُطلب منك "
            "تسجيل الدخول مرة أخرى. يجب أن تتكون كلمة المرور من 12 حرفًا على الأقل."
        ),
        keywords_en=("login", "signup", "sign in", "password", "session", "expired"),
        keywords_ar=("تسجيل الدخول", "إنشاء حساب", "كلمة المرور", "الجلسة", "انتهت الصلاحية"),
    ),
    Article(
        slug="creating-a-project",
        category="projects",
        title_en="Creating and organizing projects",
        title_ar="إنشاء المشاريع وتنظيمها",
        body_en=(
            "Projects group documents and conversations under a name and optional code (e.g. "
            "PRJ-1042). Open Projects, select New project, fill in a name, and save. Owners, "
            "admins, and managers can create, edit, and archive projects; members can view them. "
            "Only owners and admins can permanently delete a project."
        ),
        body_ar=(
            "تجمع المشاريع المستندات والمحادثات تحت اسم ورمز اختياري (مثل PRJ-1042). افتح "
            "المشاريع، اختر مشروع جديد، أدخل اسمًا واحفظ. يمكن للمالكين والمسؤولين والمديرين "
            "إنشاء المشاريع وتعديلها وأرشفتها؛ ويمكن للأعضاء عرضها فقط. يمكن للمالكين والمسؤولين "
            "فقط حذف مشروع نهائيًا."
        ),
        keywords_en=("project", "create", "organize", "code"),
        keywords_ar=("مشروع", "إنشاء", "تنظيم", "رمز"),
    ),
    Article(
        slug="uploading-a-document",
        category="documents",
        title_en="Uploading a document",
        title_ar="رفع مستند",
        body_en=(
            "From Documents, select Upload document, choose a PDF, Word, or Excel file, pick a "
            "document type (contract, BOQ, quotation, invoice, purchase order, project report, or "
            "other), and optionally attach it to a project. Only owners, admins, and managers can "
            "upload. If the upload is rejected, check that the file is a supported type and under "
            "the size limit."
        ),
        body_ar=(
            "من صفحة المستندات، اختر رفع مستند، ثم اختر ملف PDF أو Word أو Excel، وحدد نوع "
            "المستند (عقد، جدول كميات، عرض سعر، فاتورة، أمر شراء، تقرير مشروع، أو أخرى)، ويمكن "
            "ربطه بمشروع اختياريًا. يمكن للمالكين والمسؤولين والمديرين فقط الرفع. إذا رُفض الرفع، "
            "تحقق من أن الملف من نوع مدعوم وضمن الحد الأقصى للحجم."
        ),
        keywords_en=("upload", "file", "pdf", "word", "excel", "document type"),
        keywords_ar=("رفع", "ملف", "نوع المستند"),
    ),
    Article(
        slug="document-lifecycle-explained",
        category="upload_processing_indexing",
        title_en="Understanding the document lifecycle: Uploaded, Processing, Processed, Indexing, Ready",
        title_ar="فهم دورة حياة المستند: تم الرفع، قيد المعالجة، تمت المعالجة، قيد الفهرسة، جاهز",
        body_en=(
            "A document moves through five stages: Uploaded, Processing, Processed, Indexing, and "
            "Ready. Processing extracts and prepares the document's text. Indexing makes that text "
            "searchable for Ask Your Business and the Daily Brief. Both steps are explicit actions "
            "you (or a manager/admin/owner) trigger from the document's page -- this product does "
            "not process or index documents automatically in the background. A document only "
            "becomes usable in Ask Your Business once it reaches Ready."
        ),
        body_ar=(
            "يمر المستند بخمس مراحل: تم الرفع، قيد المعالجة، تمت المعالجة، قيد الفهرسة، وجاهز. "
            "تستخرج المعالجة نص المستند وتُجهزه. تجعل الفهرسة هذا النص قابلاً للبحث في اسأل عن "
            "أعمالك والموجز اليومي. كلتا الخطوتين إجراءان صريحان يُشغّلهما المستخدم (أو مدير أو "
            "مسؤول أو مالك) من صفحة المستند — هذا المنتج لا يعالج أو يفهرس المستندات تلقائيًا في "
            "الخلفية. لا يصبح المستند قابلاً للاستخدام في اسأل عن أعمالك إلا عند وصوله إلى جاهز."
        ),
        keywords_en=(
            "processing",
            "indexing",
            "ready",
            "lifecycle",
            "stuck",
            "not ready",
            "status",
        ),
        keywords_ar=("معالجة", "فهرسة", "جاهز", "دورة الحياة", "عالق", "غير جاهز", "الحالة"),
    ),
    Article(
        slug="why-document-not-ready",
        category="upload_processing_indexing",
        title_en="Why is my document not Ready?",
        title_ar="لماذا مستندي غير جاهز؟",
        body_en=(
            "Check the document's status badge on its detail page. 'Uploaded' means processing "
            "hasn't been started yet -- select Process. 'Processing' or 'Indexing' means it's "
            "actively running; wait for it to finish. 'Processing failed' or 'Indexing failed' "
            "shows a short, safe error message and a Retry button. If a retry keeps failing, "
            "report a problem and include the document so our team can look into the specific "
            "error."
        ),
        body_ar=(
            "تحقق من شارة حالة المستند في صفحة تفاصيله. 'تم الرفع' تعني أن المعالجة لم تبدأ بعد "
            "— اختر معالجة. 'قيد المعالجة' أو 'قيد الفهرسة' تعني أنها قيد التنفيذ حاليًا؛ انتظر "
            "حتى تنتهي. 'فشلت المعالجة' أو 'فشلت الفهرسة' تعرض رسالة خطأ قصيرة وآمنة وزر إعادة "
            "المحاولة. إذا استمر الفشل بعد إعادة المحاولة، أبلغ عن مشكلة وأرفق المستند حتى يتمكن "
            "فريقنا من مراجعة الخطأ المحدد."
        ),
        keywords_en=("not ready", "failed", "stuck", "retry", "error", "processing failed"),
        keywords_ar=("غير جاهز", "فشل", "عالق", "إعادة المحاولة", "خطأ"),
    ),
    Article(
        slug="asking-your-business",
        category="ask_your_business",
        title_en="Asking questions about your business",
        title_ar="طرح الأسئلة حول أعمالك",
        body_en=(
            "Ask Your Business answers questions using only your company's Ready documents, and "
            "always cites its sources. Start a conversation, type a question, and you'll get an "
            "answer with citation chips pointing to the exact document and page, sheet, or "
            "section. If nothing in your documents supports an answer, you'll be told there isn't "
            "enough information rather than getting a guess."
        ),
        body_ar=(
            "يجيب اسأل عن أعمالك على الأسئلة باستخدام مستندات شركتك الجاهزة فقط، ويذكر مصادره "
            "دائمًا. ابدأ محادثة، اكتب سؤالًا، وستحصل على إجابة مع رقاقات استشهاد تشير إلى المستند "
            "والصفحة أو الورقة أو القسم بالضبط. إذا لم يدعم أي شيء في مستنداتك إجابة، سيُخبرك "
            "النظام بعدم وجود معلومات كافية بدلاً من التخمين."
        ),
        keywords_en=("ask", "question", "conversation", "grounded", "insufficient information"),
        keywords_ar=("اسأل", "سؤال", "محادثة", "معلومات كافية"),
    ),
    Article(
        slug="understanding-citations",
        category="ask_your_business",
        title_en="Understanding citations",
        title_ar="فهم الاستشهادات",
        body_en=(
            "Every grounded answer shows one or more citation chips below it. Selecting a chip "
            "opens the exact source document. A citation always names a real page, sheet, or "
            "section in one of your own documents -- the assistant never shows a citation for "
            "information it made up."
        ),
        body_ar=(
            "تُظهر كل إجابة مستندة رقاقة استشهاد واحدة أو أكثر أسفلها. يؤدي اختيار رقاقة إلى فتح "
            "المستند المصدر بالضبط. يذكر الاستشهاد دائمًا صفحة أو ورقة أو قسمًا حقيقيًا في أحد "
            "مستنداتك — لا يُظهر المساعد استشهادًا لمعلومات اختلقها."
        ),
        keywords_en=("citation", "source", "page", "sheet", "section"),
        keywords_ar=("استشهاد", "مصدر", "صفحة", "ورقة", "قسم"),
    ),
    Article(
        slug="daily-brief-overview",
        category="daily_brief",
        title_en="Using the Daily Management Brief",
        title_ar="استخدام الموجز الإداري اليومي",
        body_en=(
            "The Daily Brief summarizes new documents and open items into New Information, "
            "Pending Actions, Follow-ups, and Potential Issues, each with a priority and a link "
            "back to its source document. Owners, admins, and managers can generate or regenerate "
            "today's brief; members can view it. It's generated on demand, not on a schedule."
        ),
        body_ar=(
            "يلخّص الموجز اليومي المستندات الجديدة والبنود المفتوحة إلى معلومات جديدة، إجراءات "
            "معلّقة، متابعات، ومشكلات محتملة، لكل منها أولوية ورابط يعود إلى مستندها المصدر. "
            "يمكن للمالكين والمسؤولين والمديرين إنشاء موجز اليوم أو إعادة إنشائه؛ ويمكن للأعضاء "
            "عرضه فقط. يُنشأ عند الطلب، وليس وفق جدول زمني."
        ),
        keywords_en=("brief", "daily", "summary", "generate", "regenerate"),
        keywords_ar=("موجز", "يومي", "ملخص", "إنشاء", "إعادة إنشاء"),
    ),
    Article(
        slug="switching-language",
        category="language_settings",
        title_en="Switching between English and Arabic",
        title_ar="التبديل بين الإنجليزية والعربية",
        body_en=(
            "Use the EN / العربية switcher in the top bar to change the interface language. "
            "Arabic automatically switches the whole layout to right-to-left. Your choice is "
            "remembered on this device for future visits."
        ),
        body_ar=(
            "استخدم مبدّل EN / العربية في الشريط العلوي لتغيير لغة الواجهة. يبدّل العربية تلقائيًا "
            "التخطيط بالكامل إلى الاتجاه من اليمين إلى اليسار. يُحفظ اختيارك على هذا الجهاز للزيارات "
            "المستقبلية."
        ),
        keywords_en=("language", "arabic", "english", "rtl", "switch"),
        keywords_ar=("لغة", "عربي", "إنجليزي", "اتجاه"),
    ),
    Article(
        slug="roles-and-permissions",
        category="roles_permissions",
        title_en="Roles and what each one can do",
        title_ar="الأدوار وما يمكن لكل دور فعله",
        body_en=(
            "There are four roles: Owner, Admin, Manager, and Member. Owners and admins have the "
            "widest access, including the audit log and team list. Owners, admins, and managers "
            "can create projects, upload documents, and generate briefs. Members can view "
            "projects, documents, and briefs, and use Ask Your Business, but cannot upload, "
            "generate briefs, or delete anything. Only owners and admins can delete documents or "
            "projects. Team invitations and role changes are not available yet in this release."
        ),
        body_ar=(
            "توجد أربعة أدوار: مالك، مسؤول، مدير، وعضو. يتمتع المالكون والمسؤولون بأوسع صلاحيات "
            "الوصول، بما في ذلك سجل التدقيق وقائمة الفريق. يمكن للمالكين والمسؤولين والمديرين "
            "إنشاء المشاريع ورفع المستندات وإنشاء الموجزات. يمكن للأعضاء عرض المشاريع والمستندات "
            "والموجزات، واستخدام اسأل عن أعمالك، لكن لا يمكنهم الرفع أو إنشاء الموجزات أو حذف أي "
            "شيء. يمكن للمالكين والمسؤولين فقط حذف المستندات أو المشاريع. دعوات الفريق وتغيير "
            "الأدوار غير متاحة بعد في هذا الإصدار."
        ),
        keywords_en=("role", "permission", "owner", "admin", "manager", "member", "cannot delete"),
        keywords_ar=("دور", "صلاحية", "مالك", "مسؤول", "مدير", "عضو", "لا يمكن الحذف"),
    ),
    Article(
        slug="cannot-delete-document",
        category="roles_permissions",
        title_en="Why can't I delete this document?",
        title_ar="لماذا لا أستطيع حذف هذا المستند؟",
        body_en=(
            "Deleting a document is restricted to owners and admins, to prevent accidental loss "
            "of shared company records. If you need a document removed and you're a manager or "
            "member, ask an owner or admin on your team, or report a problem here and we can "
            "advise."
        ),
        body_ar=(
            "يقتصر حذف المستند على المالكين والمسؤولين، لمنع الفقدان العرضي لسجلات الشركة "
            "المشتركة. إذا كنت بحاجة إلى إزالة مستند وأنت مدير أو عضو، اطلب من مالك أو مسؤول في "
            "فريقك، أو أبلغ عن مشكلة هنا وسنقدم لك النصيحة."
        ),
        keywords_en=("delete", "cannot delete", "permission denied", "document"),
        keywords_ar=("حذف", "لا يمكن الحذف", "رفض الصلاحية"),
    ),
    Article(
        slug="general-troubleshooting",
        category="troubleshooting",
        title_en="General troubleshooting tips",
        title_ar="نصائح عامة لاستكشاف الأخطاء وإصلاحها",
        body_en=(
            "If something looks wrong: refresh the page, confirm you're signed in, and check the "
            "status badges on Documents or the Daily Brief for a safe error message. If a page "
            "shows a generic error, note any reference code shown and include it when you report "
            "a problem -- it helps us find exactly what happened without needing technical details "
            "from you."
        ),
        body_ar=(
            "إذا بدا أن هناك خطأ ما: أعد تحميل الصفحة، وتأكد من أنك مسجّل الدخول، وتحقق من شارات "
            "الحالة في المستندات أو الموجز اليومي بحثًا عن رسالة خطأ آمنة. إذا ظهرت رسالة خطأ عامة "
            "في صفحة ما، لاحظ أي رمز مرجعي معروض وأرفقه عند الإبلاغ عن مشكلة — فهذا يساعدنا على "
            "تحديد ما حدث بالضبط دون الحاجة إلى تفاصيل تقنية منك."
        ),
        keywords_en=("troubleshoot", "error", "reference", "problem", "something went wrong"),
        keywords_ar=("استكشاف الأخطاء", "خطأ", "مرجع", "مشكلة"),
    ),
)

ARTICLES_BY_SLUG: dict[str, Article] = {a.slug: a for a in ARTICLES}

