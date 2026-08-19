import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  LogIn, UserPlus, LogOut, Plus, X, Trash2, ArrowDownLeft, ArrowUpRight,
  Wallet, Users, Receipt, BarChart3, LayoutGrid, Search, ChevronRight, Loader2, AlertCircle,
  Pencil, Download, ShieldCheck, ShieldOff, UserCog, Menu, Landmark, Coins, Banknote
} from "lucide-react";

/* ---------------------------------------------------------
   بياع الحلويين — Sweets Vendor Ledger
   Design language: an accountant's ledger book.
   Deep ledger-green + aged paper + gold ink accents,
   dotted leader lines between labels and figures,
   tabular numerals, a serif "stamped" display face.
--------------------------------------------------------- */

const COLORS = {
  ink: "#1A1416",
  inkSoft: "#6E5B63",
  paper: "#FFF7FB",
  paperAlt: "#FBE7F0",
  card: "#FFFFFF",
  ledger: "#E81973",
  ledgerDark: "#0C0C0C",
  ledgerLight: "#F2549A",
  gold: "#9B0F52",
  goldSoft: "#F3A6C9",
  brick: "#9B3E36",
  brickSoft: "#F3E1DE",
  line: "#F0D3E1",
};

const LOGO_SRC = "/logo.png";


/* Reliable viewport detection via JS (not CSS media queries / Tailwind responsive
   classes), since this environment only renders a fixed subset of Tailwind and does
   not reliably apply custom <style> rules either. */
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(() => (typeof window !== "undefined" ? window.innerWidth >= 1024 : false));
  useEffect(() => {
    const onResize = () => setIsDesktop(window.innerWidth >= 1024);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return isDesktop;
}

const KEYS = {
  users: "ledger_users_v2",
  customers: "ledger_customers_v2",
  customerTransactions: "ledger_customer_tx_v2",
  treasury: "ledger_treasury_v2",
  session: "ledger_session_v1",
};

function genId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function fmt(n) {
  const num = Number(n) || 0;
  return num.toLocaleString("ar-EG", { maximumFractionDigits: 2 });
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// These keep the exact same names/signatures as the Claude-artifact version
// (storageGet/storageSet/storageDelete), but talk to the browser's own
// localStorage instead of window.storage - so the rest of the app didn't
// need to change at all. The "shared" parameter is accepted for API
// compatibility but ignored (there's only one local device here).
async function storageGet(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

async function storageSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

async function storageDelete(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore - nothing to delete */
  }
}

/* ---------------------------------- UI atoms ---------------------------------- */

function Button({ children, onClick, variant = "primary", type = "button", className = "", disabled }) {
  const base = "font-body font-semibold rounded-lg px-4 py-2.5 flex items-center justify-center gap-2 transition-transform active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100";
  const styles = {
    primary: { background: COLORS.ledger, color: "#fff" },
    gold: { background: COLORS.gold, color: "#fff" },
    ghost: { background: "transparent", color: COLORS.ledger, border: `1.5px solid ${COLORS.ledger}` },
    danger: { background: COLORS.brickSoft, color: COLORS.brick },
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${className}`} style={styles[variant]}>
      {children}
    </button>
  );
}

function Field({ label, children }) {
  return (
    <label className="block mb-4">
      <span className="font-body text-sm font-semibold block mb-1.5" style={{ color: COLORS.inkSoft }}>{label}</span>
      {children}
    </label>
  );
}

function inputStyle() {
  return {
    width: "100%",
    background: COLORS.paperAlt,
    border: `1.5px solid ${COLORS.line}`,
    borderRadius: "8px",
    padding: "10px 12px",
    color: COLORS.ink,
    fontFamily: "Cairo, sans-serif",
  };
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(30,42,34,0.55)" }} onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl p-5 sm:p-6 shadow-2xl"
        style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-display text-xl font-bold" style={{ color: COLORS.ledger }}>{title}</h3>
          <button onClick={onClose} className="p-1 rounded-full hover:opacity-70" style={{ color: COLORS.inkSoft }}>
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function LedgerRow({ label, value, bold, color }) {
  return (
    <div className="flex items-baseline py-1">
      <span className="font-body text-sm" style={{ color: COLORS.inkSoft }}>{label}</span>
      <span className="dotted-leader" />
      <span className={`tabular font-body ${bold ? "font-extrabold text-lg" : "font-semibold"}`} style={{ color: color || COLORS.ink }}>
        {value}
      </span>
    </div>
  );
}

function EmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="p-4 rounded-full mb-4" style={{ background: COLORS.paperAlt }}>
        <Icon size={28} color={COLORS.gold} />
      </div>
      <p className="font-body font-bold" style={{ color: COLORS.ink }}>{title}</p>
      <p className="font-body text-sm mt-1" style={{ color: COLORS.inkSoft }}>{subtitle}</p>
    </div>
  );
}

/* ---------------------------------- Auth screens ---------------------------------- */

function AuthShell({ children }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-5" style={{ background: COLORS.paper }} dir="rtl">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div
            className="inline-flex items-center justify-center w-24 h-24 rounded-2xl mb-4 shadow-lg overflow-hidden"
            style={{ background: COLORS.ledgerDark, border: `2px solid ${COLORS.ledger}` }}
          >
            <img src={LOGO_SRC} alt="بياع الحلويين" className="w-full h-full object-cover" />
          </div>
          <h1 className="font-display text-3xl font-bold" style={{ color: COLORS.ledger }}>بياع الحلويين</h1>
          <p className="font-body text-sm mt-1" style={{ color: COLORS.inkSoft }}>سجلّ الدفعات والمصاريف بدقة</p>
        </div>
        <div className="rounded-2xl p-6 shadow-lg" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          {children}
        </div>
      </div>
    </div>
  );
}

function LoginScreen({ onLogin, goRegister, users, loading, onResetAll }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [confirmingReset, setConfirmingReset] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    const user = users.find((u) => u.username === username.trim() && u.password === password.trim());
    if (!user) {
      setError("اسم المستخدم أو كلمة المرور غير صحيحة");
      return;
    }
    setError("");
    onLogin(user);
  };

  return (
    <AuthShell>
      <form onSubmit={submit}>
        <Field label="اسم المستخدم">
          <input style={inputStyle()} value={username} onChange={(e) => setUsername(e.target.value)} placeholder="ادخل اسم المستخدم" autoCapitalize="none" autoCorrect="off" autoComplete="username" spellCheck="false" required />
        </Field>
        <Field label="كلمة المرور">
          <input style={inputStyle()} type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoCapitalize="none" autoCorrect="off" autoComplete="current-password" spellCheck="false" required />
        </Field>
        {error && (
          <div className="flex items-center gap-2 mb-4 text-sm font-body" style={{ color: COLORS.brick }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? <Loader2 size={18} className="animate-spin" /> : <LogIn size={18} />}
          تسجيل الدخول
        </Button>
        <p className="text-center font-body text-sm mt-4" style={{ color: COLORS.inkSoft }}>
          لا تملك حساباً؟{" "}
          <button type="button" onClick={goRegister} className="font-bold" style={{ color: COLORS.gold }}>
            إنشاء حساب جديد
          </button>
        </p>
        {error && (
          <div className="mt-4 pt-4 text-center" style={{ borderTop: `1px dashed ${COLORS.line}` }}>
            {!confirmingReset ? (
              <button
                type="button"
                onClick={() => setConfirmingReset(true)}
                className="font-body text-xs"
                style={{ color: COLORS.inkSoft, textDecoration: "underline" }}
              >
                نسيت بيانات الدخول ولا يمكنني الوصول لأي حساب؟
              </button>
            ) : (
              <div>
                <p className="font-body text-xs mb-2" style={{ color: COLORS.brick }}>
                  هذا سيمسح كل الحسابات والموردين والدفعات والمصاريف نهائيًا ولا يمكن التراجع. استخدمه فقط لو كل الحسابات مفقودة.
                </p>
                <div className="flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => setConfirmingReset(false)}
                    className="font-body text-xs px-3 py-1.5 rounded-lg"
                    style={{ color: COLORS.inkSoft, background: COLORS.paperAlt }}
                  >
                    إلغاء
                  </button>
                  <button
                    type="button"
                    onClick={onResetAll}
                    className="font-body text-xs px-3 py-1.5 rounded-lg font-bold"
                    style={{ color: "#fff", background: COLORS.brick }}
                  >
                    نعم، امسح كل البيانات وابدأ من جديد
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </form>
    </AuthShell>
  );
}

function RegisterScreen({ onRegister, goLogin, users, loading, serverError }) {
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (users.some((u) => u.username === username.trim())) {
      setError("اسم المستخدم موجود بالفعل، اختر اسماً آخر");
      return;
    }
    if (password.trim().length < 4) {
      setError("كلمة المرور يجب ألا تقل عن 4 أحرف");
      return;
    }
    setError("");
    onRegister({ id: genId(), name: name.trim(), username: username.trim(), password: password.trim(), createdAt: Date.now() });
  };

  const shownError = error || serverError;

  return (
    <AuthShell>
      <form onSubmit={submit}>
        <Field label="الاسم الكامل">
          <input style={inputStyle()} value={name} onChange={(e) => setName(e.target.value)} placeholder="اسمك" required />
        </Field>
        <Field label="اسم المستخدم">
          <input style={inputStyle()} value={username} onChange={(e) => setUsername(e.target.value)} placeholder="اختر اسم مستخدم" autoCapitalize="none" autoCorrect="off" autoComplete="username" spellCheck="false" required />
        </Field>
        <Field label="كلمة المرور">
          <input style={inputStyle()} type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="4 أحرف على الأقل" autoCapitalize="none" autoCorrect="off" autoComplete="new-password" spellCheck="false" required />
        </Field>
        {shownError && (
          <div className="flex items-center gap-2 mb-4 text-sm font-body" style={{ color: COLORS.brick }}>
            <AlertCircle size={16} /> {shownError}
          </div>
        )}
        <Button type="submit" variant="gold" className="w-full" disabled={loading}>
          {loading ? <Loader2 size={18} className="animate-spin" /> : <UserPlus size={18} />}
          إنشاء الحساب
        </Button>
        <p className="text-center font-body text-sm mt-4" style={{ color: COLORS.inkSoft }}>
          لديك حساب بالفعل؟{" "}
          <button type="button" onClick={goLogin} className="font-bold" style={{ color: COLORS.gold }}>
            تسجيل الدخول
          </button>
        </p>
      </form>
    </AuthShell>
  );
}

/* ---------------------------------- Layout ---------------------------------- */

function NavItem({ icon: Icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl font-body font-semibold text-sm transition-colors"
      style={{
        background: active ? "rgba(180,136,58,0.15)" : "transparent",
        color: active ? COLORS.goldSoft : "rgba(246,243,234,0.75)",
      }}
    >
      <Icon size={18} />
      {label}
    </button>
  );
}

function Sidebar({ tab, setTab, currentUser, onLogout, mobileOpen, onClose, isDesktop }) {
  const isAdmin = currentUser.role === "admin";
  const items = [
    { key: "dashboard", label: "لوحة التحكم", icon: LayoutGrid },
    { key: "customers", label: "العملاء", icon: Users },
    { key: "treasury", label: "الخزينة", icon: Landmark },
    { key: "reports", label: "التقارير", icon: BarChart3 },
    ...(isAdmin ? [{ key: "users", label: "المستخدمون", icon: UserCog }] : []),
  ];

  const sidebarStyle = isDesktop
    ? { background: COLORS.ledgerDark, position: "sticky", top: 0, height: "100vh", width: 256, flexShrink: 0 }
    : {
        background: COLORS.ledgerDark,
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "min(300px, 82vw)",
        zIndex: 40,
        transform: mobileOpen ? "translateX(0)" : "translateX(100%)",
        transition: "transform 0.25s ease",
        overflowY: "auto",
      };

  return (
    <div className="flex flex-col p-4 no-print" style={sidebarStyle}>
      <div className="flex items-center justify-between px-2 py-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center overflow-hidden" style={{ background: COLORS.ledger }}>
            <img src={LOGO_SRC} alt="بياع الحلويين" className="w-full h-full object-cover" />
          </div>
          <span className="font-display text-lg font-bold" style={{ color: COLORS.paper }}>بياع الحلويين</span>
        </div>
        {!isDesktop && (
          <button onClick={onClose} className="p-1 rounded-lg" style={{ color: "rgba(246,243,234,0.7)" }}>
            <X size={20} />
          </button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {items.map((it) => (
          <NavItem key={it.key} icon={it.icon} label={it.label} active={tab === it.key} onClick={() => setTab(it.key)} />
        ))}
      </div>
      <div className="mt-auto pt-4" style={{ borderTop: "1px solid rgba(246,243,234,0.15)" }}>
        <div className="px-2 mb-2">
          <p className="font-body text-sm font-bold flex items-center gap-1.5" style={{ color: COLORS.paper }}>
            {currentUser.name}
            {isAdmin && <ShieldCheck size={13} color={COLORS.goldSoft} />}
          </p>
          <p className="font-body text-xs" style={{ color: "rgba(246,243,234,0.6)" }}>@{currentUser.username} · {isAdmin ? "مسؤول" : "موظف"}</p>
        </div>
        <button onClick={onLogout} className="w-full flex items-center gap-2 px-2 py-2 rounded-lg font-body text-sm font-semibold" style={{ color: COLORS.brickSoft }}>
          <LogOut size={16} /> تسجيل الخروج
        </button>
      </div>
    </div>
  );
}

function MobileTopBar({ onOpenMenu, tab }) {
  const titles = { dashboard: "لوحة التحكم", customers: "العملاء", treasury: "الخزينة", reports: "التقارير", users: "المستخدمون" };
  return (
    <div
      className="flex items-center justify-between px-4 py-3 no-print"
      style={{ background: COLORS.ledgerDark, position: "sticky", top: 0, zIndex: 20 }}
    >
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-md flex items-center justify-center overflow-hidden" style={{ background: COLORS.ledger }}>
          <img src={LOGO_SRC} alt="بياع الحلويين" className="w-full h-full object-cover" />
        </div>
        <span className="font-display text-base font-bold" style={{ color: COLORS.paper }}>{titles[tab] || "بياع الحلويين"}</span>
      </div>
      <button onClick={onOpenMenu} className="p-1.5 rounded-lg" style={{ color: COLORS.paper }}>
        <Menu size={22} />
      </button>
    </div>
  );
}

function TopBar({ title, action }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-5 sm:mb-6">
      <h2 className="font-display text-xl sm:text-2xl font-bold" style={{ color: COLORS.ledger }}>{title}</h2>
      {action && <div className="no-print">{action}</div>}
    </div>
  );
}

/* ---------------------------------- Dashboard ---------------------------------- */

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
      <div className="flex items-center justify-between mb-2 sm:mb-3">
        <div className="p-2 rounded-lg" style={{ background: `${color}1A` }}>
          <Icon size={18} color={color} />
        </div>
      </div>
      <p className="font-body text-xs sm:text-sm mb-1" style={{ color: COLORS.inkSoft }}>{label}</p>
      <p className="tabular font-display text-xl sm:text-2xl font-bold" style={{ color: COLORS.ink }}>{fmt(value)}</p>
    </div>
  );
}

function Dashboard({ customers, customerTx, treasury, isAdmin }) {
  const totalPaid = customerTx.filter((t) => t.type === "paid").reduce((s, t) => s + Number(t.amount), 0);
  const totalDue = customerTx.filter((t) => t.type === "due").reduce((s, t) => s + Number(t.amount), 0);
  const totalCash = treasury.filter((t) => t.type === "cash").reduce((s, t) => s + Number(t.amount), 0);
  const totalExpense = treasury.filter((t) => t.type === "expense").reduce((s, t) => s + Number(t.amount), 0);
  const netTreasury = totalCash - totalExpense;
  const recent = [...customerTx].sort((a, b) => b.createdAt - a.createdAt).slice(0, 6);

  return (
    <div>
      <TopBar title="لوحة التحكم" />
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          هذه البيانات تعرض فقط ما أضفته أنت. المسؤول يمكنه رؤية بيانات جميع المستخدمين.
        </p>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <StatCard icon={Users} label="عدد العملاء" value={customers.length} color={COLORS.ledger} />
        <StatCard icon={ArrowDownLeft} label="إجمالي المدفوع من العملاء" value={totalPaid} color={COLORS.ledgerLight} />
        <StatCard icon={ArrowUpRight} label="إجمالي المستحق على العملاء" value={totalDue} color={COLORS.brick} />
        <StatCard icon={Landmark} label="صافي الخزينة" value={netTreasury} color={netTreasury >= 0 ? COLORS.gold : COLORS.brick} />
      </div>
      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-3" style={{ color: COLORS.ink }}>آخر حركات العملاء</h3>
        {recent.length === 0 ? (
          <EmptyState icon={Users} title="لا توجد حركات بعد" subtitle="ابدأ بإضافة عميل ثم سجّل أول حركة" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {recent.map((t) => {
              const c = customers.find((cu) => cu.id === t.customerId);
              return (
                <div key={t.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-full" style={{ background: t.type === "due" ? COLORS.brickSoft : "rgba(242,84,154,0.12)" }}>
                      {t.type === "due" ? <ArrowUpRight size={15} color={COLORS.brick} /> : <ArrowDownLeft size={15} color={COLORS.ledgerLight} />}
                    </div>
                    <div>
                      <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>{c ? c.name : "عميل محذوف"}</p>
                      <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{t.type === "due" ? "مستحق" : "مدفوع"} · {t.date}</p>
                    </div>
                  </div>
                  <span className="tabular font-body font-bold" style={{ color: COLORS.ink }}>{fmt(t.amount)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------- Customers ---------------------------------- */

function CustomerFormModal({ onClose, onSave, initial }) {
  const isEdit = Boolean(initial);
  const [name, setName] = useState(initial?.name || "");
  const [phone, setPhone] = useState(initial?.phone || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  return (
    <Modal title={isEdit ? "تعديل بيانات العميل" : "إضافة عميل جديد"} onClose={onClose}>
      <Field label="اسم العميل">
        <input style={inputStyle()} value={name} onChange={(e) => setName(e.target.value)} placeholder="اسم العميل" />
      </Field>
      <Field label="رقم الهاتف (اختياري)">
        <input style={inputStyle()} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="01xxxxxxxxx" />
      </Field>
      <Field label="ملاحظات (اختياري)">
        <textarea style={{ ...inputStyle(), minHeight: 70 }} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <Button
        className="w-full"
        onClick={() => {
          if (!name.trim()) return;
          if (isEdit) onSave({ ...initial, name: name.trim(), phone: phone.trim(), notes: notes.trim() });
          else onSave({ id: genId(), name: name.trim(), phone: phone.trim(), notes: notes.trim(), createdAt: Date.now() });
        }}
      >
        {isEdit ? <Pencil size={18} /> : <Plus size={18} />} {isEdit ? "حفظ التعديلات" : "حفظ العميل"}
      </Button>
    </Modal>
  );
}

function CustomersView({ customers, customerTx, onAdd, onEdit, onDelete, onOpen, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [query, setQuery] = useState("");

  const balanceOf = (id) => {
    const list = customerTx.filter((t) => t.customerId === id);
    const paid = list.filter((t) => t.type === "paid").reduce((s, t) => s + Number(t.amount), 0);
    const due = list.filter((t) => t.type === "due").reduce((s, t) => s + Number(t.amount), 0);
    return due - paid;
  };

  const filtered = customers.filter((c) => c.name.includes(query) || (c.phone || "").includes(query));

  return (
    <div>
      <TopBar
        title="العملاء"
        action={<Button onClick={() => setShowAdd(true)}><Plus size={16} /> عميل جديد</Button>}
      />
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          تظهر هنا فقط العملاء الذين أضفتهم أنت.
        </p>
      )}
      <div className="relative mb-4 max-w-sm">
        <Search size={16} className="absolute top-1/2 -translate-y-1/2 right-3" color={COLORS.inkSoft} />
        <input style={{ ...inputStyle(), paddingRight: 34 }} placeholder="بحث عن عميل..." value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={Users} title="لا يوجد عملاء" subtitle="أضف أول عميل لبدء تسجيل حركاته" />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((c) => {
            const bal = balanceOf(c.id);
            return (
              <div
                key={c.id}
                onClick={() => onOpen(c.id)}
                className="rounded-2xl p-5 cursor-pointer hover:shadow-md transition-shadow"
                style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center font-display font-bold" style={{ background: COLORS.paperAlt, color: COLORS.ledger }}>
                    {c.name.charAt(0)}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditing(c); }}
                      className="p-1.5 rounded-lg hover:opacity-70"
                      style={{ color: COLORS.inkSoft }}
                    >
                      <Pencil size={15} />
                    </button>
                    {isAdmin && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
                        className="p-1.5 rounded-lg hover:opacity-70"
                        style={{ color: COLORS.brick }}
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>
                </div>
                <p className="font-body font-bold mb-1" style={{ color: COLORS.ink }}>{c.name}</p>
                {c.phone && <p className="font-body text-xs mb-3" style={{ color: COLORS.inkSoft }}>{c.phone}</p>}
                <LedgerRow
                  label="المستحق عليه"
                  value={fmt(Math.abs(bal))}
                  bold
                  color={bal > 0 ? COLORS.brick : bal < 0 ? COLORS.ledgerLight : COLORS.inkSoft}
                />
                <p className="font-body text-xs mt-1" style={{ color: COLORS.inkSoft }}>
                  {bal > 0 ? "عليه مبلغ مستحق" : bal < 0 ? "له رصيد زائد" : "متوازن"}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {showAdd && (
        <CustomerFormModal
          onClose={() => setShowAdd(false)}
          onSave={(cust) => { onAdd(cust); setShowAdd(false); }}
        />
      )}
      {editing && (
        <CustomerFormModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={(cust) => { onEdit(cust); setEditing(null); }}
        />
      )}
    </div>
  );
}

/* ---------------------------------- Customer detail ---------------------------------- */

function CustomerTransactionFormModal({ onClose, onSave, initial }) {
  const isEdit = Boolean(initial);
  const [type, setType] = useState(initial?.type || "paid");
  const [amount, setAmount] = useState(initial ? String(initial.amount) : "");
  const [date, setDate] = useState(initial?.date || todayStr());
  const [note, setNote] = useState(initial?.note || "");

  return (
    <Modal title={isEdit ? "تعديل حركة" : "إضافة حركة"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 mb-4">
        <button
          onClick={() => setType("paid")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "paid" ? COLORS.ledgerLight : COLORS.paperAlt, color: type === "paid" ? "#fff" : COLORS.inkSoft }}
        >
          <ArrowDownLeft size={15} /> مدفوع
        </button>
        <button
          onClick={() => setType("due")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "due" ? COLORS.brick : COLORS.paperAlt, color: type === "due" ? "#fff" : COLORS.inkSoft }}
        >
          <ArrowUpRight size={15} /> مستحق
        </button>
      </div>
      <Field label="المبلغ">
        <input style={inputStyle()} type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
      </Field>
      <Field label="التاريخ">
        <input style={inputStyle()} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </Field>
      <Field label="ملاحظة (اختياري)">
        <input style={inputStyle()} value={note} onChange={(e) => setNote(e.target.value)} placeholder="سبب الحركة" />
      </Field>
      <Button
        className="w-full"
        variant={type === "due" ? "danger" : "primary"}
        onClick={() => {
          if (!(Number(amount) > 0)) return;
          if (isEdit) onSave({ ...initial, type, amount: Number(amount), date, note: note.trim() });
          else onSave({ id: genId(), type, amount: Number(amount), date, note: note.trim(), createdAt: Date.now() });
        }}
      >
        {isEdit ? <Pencil size={18} /> : <Plus size={18} />} {isEdit ? "حفظ التعديلات" : "حفظ الحركة"}
      </Button>
    </Modal>
  );
}

function CustomerDetail({ customer, customerTx, onBack, onAddTx, onEditTx, onDeleteTx, onEdit, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editingTx, setEditingTx] = useState(null);
  const list = customerTx.filter((t) => t.customerId === customer.id).sort((a, b) => b.createdAt - a.createdAt);
  const paid = list.filter((t) => t.type === "paid").reduce((s, t) => s + Number(t.amount), 0);
  const due = list.filter((t) => t.type === "due").reduce((s, t) => s + Number(t.amount), 0);
  const balance = due - paid;

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1 font-body text-sm font-semibold mb-4 no-print" style={{ color: COLORS.inkSoft }}>
        <ChevronRight size={16} /> رجوع إلى العملاء
      </button>
      <TopBar
        title={customer.name}
        action={
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => setShowEdit(true)}><Pencil size={16} /> تعديل</Button>
            <Button onClick={() => setShowAdd(true)}><Plus size={16} /> إضافة حركة</Button>
          </div>
        }
      />
      {customer.phone && <p className="font-body text-sm -mt-4 mb-6" style={{ color: COLORS.inkSoft }}>{customer.phone}</p>}

      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="إجمالي المدفوع منه" value={fmt(paid)} color={COLORS.ledgerLight} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="إجمالي المستحق عليه" value={fmt(due)} color={COLORS.brick} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.ledgerDark }}>
          <p className="font-body text-sm mb-1" style={{ color: "rgba(246,243,234,0.7)" }}>الرصيد الصافي</p>
          <p className="tabular font-display text-2xl font-bold" style={{ color: COLORS.goldSoft }}>{fmt(Math.abs(balance))}</p>
          <p className="font-body text-xs mt-1" style={{ color: "rgba(246,243,234,0.6)" }}>
            {balance > 0 ? "عليه مبلغ مستحق" : balance < 0 ? "له رصيد زائد" : "متوازن"}
          </p>
        </div>
      </div>

      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-3" style={{ color: COLORS.ink }}>سجل الحركات</h3>
        {list.length === 0 ? (
          <EmptyState icon={Wallet} title="لا توجد حركات مسجلة" subtitle="أضف أول حركة لهذا العميل" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {list.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full" style={{ background: t.type === "due" ? COLORS.brickSoft : "rgba(242,84,154,0.12)" }}>
                    {t.type === "due" ? <ArrowUpRight size={15} color={COLORS.brick} /> : <ArrowDownLeft size={15} color={COLORS.ledgerLight} />}
                  </div>
                  <div>
                    <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>{t.type === "due" ? "مستحق" : "مدفوع"}</p>
                    <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{t.date}{t.note ? ` · ${t.note}` : ""}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="tabular font-body font-bold" style={{ color: t.type === "due" ? COLORS.brick : COLORS.ledgerLight }}>{fmt(t.amount)}</span>
                  <button onClick={() => setEditingTx(t)} className="p-1 rounded hover:opacity-70 no-print" style={{ color: COLORS.inkSoft }}>
                    <Pencil size={14} />
                  </button>
                  {isAdmin && (
                    <button onClick={() => onDeleteTx(t.id)} className="p-1 rounded hover:opacity-70 no-print" style={{ color: COLORS.inkSoft }}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showAdd && (
        <CustomerTransactionFormModal
          onClose={() => setShowAdd(false)}
          onSave={(tx) => { onAddTx({ ...tx, customerId: customer.id }); setShowAdd(false); }}
        />
      )}
      {editingTx && (
        <CustomerTransactionFormModal
          initial={editingTx}
          onClose={() => setEditingTx(null)}
          onSave={(tx) => { onEditTx(tx); setEditingTx(null); }}
        />
      )}
      {showEdit && (
        <CustomerFormModal
          initial={customer}
          onClose={() => setShowEdit(false)}
          onSave={(cust) => { onEdit(cust); setShowEdit(false); }}
        />
      )}
    </div>
  );
}

/* ---------------------------------- Treasury (نقدية / مصروف / صافي النقدية) ---------------------------------- */

function AddTreasuryModal({ onClose, onSave }) {
  const [type, setType] = useState("cash");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayStr());
  const [note, setNote] = useState("");

  return (
    <Modal title="إضافة إلى الخزينة" onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 mb-4">
        <button
          onClick={() => setType("cash")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "cash" ? COLORS.ledgerLight : COLORS.paperAlt, color: type === "cash" ? "#fff" : COLORS.inkSoft }}
        >
          <Banknote size={15} /> مبلغ نقدي
        </button>
        <button
          onClick={() => setType("expense")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "expense" ? COLORS.brick : COLORS.paperAlt, color: type === "expense" ? "#fff" : COLORS.inkSoft }}
        >
          <Receipt size={15} /> مصروف
        </button>
      </div>
      <Field label="المبلغ">
        <input style={inputStyle()} type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
      </Field>
      <Field label="التاريخ">
        <input style={inputStyle()} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </Field>
      <Field label="ملاحظة (اختياري)">
        <input style={inputStyle()} value={note} onChange={(e) => setNote(e.target.value)} placeholder="وصف الحركة" />
      </Field>
      <Button
        className="w-full"
        variant={type === "expense" ? "danger" : "primary"}
        onClick={() => Number(amount) > 0 && onSave({ id: genId(), type, amount: Number(amount), date, note: note.trim(), createdAt: Date.now() })}
      >
        <Plus size={18} /> حفظ
      </Button>
    </Modal>
  );
}

function TreasuryView({ treasury, onAdd, onDelete, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const totalCash = treasury.filter((t) => t.type === "cash").reduce((s, t) => s + Number(t.amount), 0);
  const totalExpense = treasury.filter((t) => t.type === "expense").reduce((s, t) => s + Number(t.amount), 0);
  const net = totalCash - totalExpense;
  const sorted = [...treasury].sort((a, b) => b.createdAt - a.createdAt);

  return (
    <div>
      <TopBar title="الخزينة" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} /> إضافة مبلغ</Button>} />
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          تظهر هنا فقط المبالغ التي أضفتها أنت.
        </p>
      )}

      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="إجمالي النقدية" value={fmt(totalCash)} color={COLORS.ledgerLight} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="إجمالي المصاريف" value={fmt(totalExpense)} color={COLORS.brick} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.ledgerDark }}>
          <p className="font-body text-sm mb-1" style={{ color: "rgba(246,243,234,0.7)" }}>صافي النقدية</p>
          <p className="tabular font-display text-xl sm:text-2xl font-bold" style={{ color: net >= 0 ? COLORS.goldSoft : COLORS.brickSoft }}>{fmt(Math.abs(net))}</p>
          {net < 0 && <p className="font-body text-xs mt-1" style={{ color: "rgba(246,243,234,0.6)" }}>عجز في الخزينة</p>}
        </div>
      </div>

      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-3" style={{ color: COLORS.ink }}>سجل الخزينة</h3>
        {sorted.length === 0 ? (
          <EmptyState icon={Landmark} title="لا توجد حركات مسجلة" subtitle="أضف مبلغًا نقديًا أو مصروفًا" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {sorted.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full" style={{ background: t.type === "cash" ? "rgba(242,84,154,0.12)" : COLORS.brickSoft }}>
                    {t.type === "cash" ? <Banknote size={15} color={COLORS.ledgerLight} /> : <Receipt size={15} color={COLORS.brick} />}
                  </div>
                  <div>
                    <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>{t.type === "cash" ? "مبلغ نقدي" : "مصروف"}</p>
                    <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{t.date}{t.note ? ` · ${t.note}` : ""}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="tabular font-body font-bold" style={{ color: t.type === "cash" ? COLORS.ledgerLight : COLORS.brick }}>{fmt(t.amount)}</span>
                  {isAdmin && (
                    <button onClick={() => onDelete(t.id)} className="p-1 rounded hover:opacity-70" style={{ color: COLORS.inkSoft }}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="font-body text-xs mt-4" style={{ color: COLORS.inkSoft }}>
          هذه الخزينة مستقلة تمامًا عن حركات العملاء (المدفوع/المستحق) ولا تتأثر بها بأي شكل — الإضافة هنا يدوية فقط.
        </p>
      </div>

      {showAdd && (
        <AddTreasuryModal onClose={() => setShowAdd(false)} onSave={(t) => { onAdd(t); setShowAdd(false); }} />
      )}
    </div>
  );
}


/* ---------------------------------- Reports ---------------------------------- */

function ReportsView({ customers, customerTx, treasury, isAdmin }) {
  const totalPaid = customerTx.filter((t) => t.type === "paid").reduce((s, t) => s + Number(t.amount), 0);
  const totalDue = customerTx.filter((t) => t.type === "due").reduce((s, t) => s + Number(t.amount), 0);
  const totalCash = treasury.filter((t) => t.type === "cash").reduce((s, t) => s + Number(t.amount), 0);
  const totalExpense = treasury.filter((t) => t.type === "expense").reduce((s, t) => s + Number(t.amount), 0);
  const netTreasury = totalCash - totalExpense;

  const byCustomer = customers.map((c) => {
    const list = customerTx.filter((t) => t.customerId === c.id);
    const paid = list.filter((t) => t.type === "paid").reduce((sum, t) => sum + Number(t.amount), 0);
    const due = list.filter((t) => t.type === "due").reduce((sum, t) => sum + Number(t.amount), 0);
    return { name: c.name, net: due - paid };
  }).sort((a, b) => Math.abs(b.net) - Math.abs(a.net));

  const maxAbs = Math.max(1, ...byCustomer.map((c) => Math.abs(c.net)));

  return (
    <div className="print-area">
      <TopBar
        title="التقارير"
        action={<Button variant="ghost" onClick={() => window.print()}><Download size={16} /> تصدير PDF</Button>}
      />
      <div className="print-header mb-6">
        <h1 className="font-display text-2xl font-bold" style={{ color: COLORS.ledger }}>تقرير بياع الحلويين</h1>
        <p className="font-body text-sm" style={{ color: COLORS.inkSoft }}>بتاريخ {todayStr()}</p>
      </div>
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block no-print" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          هذا التقرير يعرض فقط البيانات التي أضفتها أنت.
        </p>
      )}
      <div className="rounded-2xl p-6 mb-6" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <LedgerRow label="إجمالي المدفوع من العملاء" value={fmt(totalPaid)} color={COLORS.ledgerLight} bold />
        <LedgerRow label="إجمالي المستحق على العملاء" value={fmt(totalDue)} color={COLORS.brick} bold />
        <div style={{ borderTop: `1px solid ${COLORS.line}`, marginTop: 8, paddingTop: 8 }}>
          <LedgerRow label="إجمالي النقدية في الخزينة" value={fmt(totalCash)} color={COLORS.ledgerLight} bold />
          <LedgerRow label="إجمالي المصاريف" value={fmt(totalExpense)} color={COLORS.brick} bold />
          <LedgerRow label="صافي الخزينة" value={fmt(netTreasury)} bold color={COLORS.ledger} />
        </div>
      </div>

      <div className="rounded-2xl p-6" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-4" style={{ color: COLORS.ink }}>الرصيد الصافي لكل عميل</h3>
        {byCustomer.length === 0 ? (
          <p className="font-body text-sm" style={{ color: COLORS.inkSoft }}>لا توجد بيانات بعد</p>
        ) : (
          <div className="flex flex-col gap-3">
            {byCustomer.map((c) => (
              <div key={c.name}>
                <div className="flex justify-between mb-1">
                  <span className="font-body text-sm font-semibold" style={{ color: COLORS.ink }}>{c.name}</span>
                  <span className="tabular font-body text-sm font-bold" style={{ color: c.net >= 0 ? COLORS.brick : COLORS.ledgerLight }}>{fmt(Math.abs(c.net))}</span>
                </div>
                <div className="h-2 rounded-full w-full" style={{ background: COLORS.paperAlt }}>
                  <div
                    className="h-2 rounded-full"
                    style={{ width: `${(Math.abs(c.net) / maxAbs) * 100}%`, background: c.net >= 0 ? COLORS.brick : COLORS.ledgerLight }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------- Users (admin) ---------------------------------- */

function BackupSection({ users, customers, customerTx, treasury, onImport }) {
  const [showExport, setShowExport] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importSuccess, setImportSuccess] = useState(false);
  const [confirmingImport, setConfirmingImport] = useState(false);
  const [copied, setCopied] = useState(false);

  const backupData = () =>
    JSON.stringify({ users, customers, customerTx, treasury, exportedAt: new Date().toISOString() }, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(backupData());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked - user can select the text manually */
    }
  };

  const handleImport = async () => {
    let parsed;
    try {
      parsed = JSON.parse(importText);
    } catch {
      setImportError("النص غير صالح كـ JSON. تأكد أنك لصقت نص النسخة الاحتياطية كاملاً بدون نقص أو تعديل (وإن لم تُستخدم علامات اقتباس ذكية عن طريق الخطأ).");
      return;
    }
    if (!parsed || typeof parsed !== "object") {
      setImportError("النص غير صالح، تأكد أنك لصقت نص النسخة الاحتياطية كاملاً كما هو");
      return;
    }
    setImportError("");
    setImportBusy(true);
    try {
      await onImport(parsed);
      setImportBusy(false);
      setImportSuccess(true);
      setConfirmingImport(false);
      setTimeout(() => {
        setShowImport(false);
        setImportSuccess(false);
        setImportText("");
      }, 1200);
    } catch (err) {
      setImportBusy(false);
      setConfirmingImport(false);
      setImportError(err?.message || "تعذّر استيراد البيانات، حاول مرة أخرى.");
    }
  };

  return (
    <div className="rounded-2xl p-4 sm:p-5 mt-6" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
      <h3 className="font-body font-bold mb-2" style={{ color: COLORS.ink }}>النسخ الاحتياطي للبيانات</h3>
      <p className="font-body text-sm mb-4" style={{ color: COLORS.inkSoft }}>
        احفظ نسخة من كل البيانات (الحسابات، العملاء، حركاتهم، والخزينة) في مكان آمن عندك، عشان تقدر تسترجعها لو احتجت تفتح نسخة جديدة من البرنامج بعد أي تعديل مستقبلي.
      </p>
      <div className="flex gap-2 flex-wrap">
        <Button variant="ghost" onClick={() => setShowExport(true)}><Download size={16} /> تصدير نسخة احتياطية</Button>
        <Button variant="ghost" onClick={() => setShowImport(true)}><UserPlus size={16} /> استيراد نسخة احتياطية</Button>
      </div>

      {showExport && (
        <Modal title="نسخة احتياطية من البيانات" onClose={() => setShowExport(false)}>
          <p className="font-body text-sm mb-3" style={{ color: COLORS.inkSoft }}>
            انسخ النص ده بالكامل واحفظه في مكان آمن (مثلاً تطبيق الملاحظات أو رسالة لنفسك). لو فتحت نسخة جديدة من البرنامج بعدين، الصق نفس النص في "استيراد نسخة احتياطية" لاسترجاع كل بياناتك.
          </p>
          <textarea
            readOnly
            value={backupData()}
            onClick={(e) => e.target.select()}
            style={{ ...inputStyle(), minHeight: 180, fontFamily: "monospace", fontSize: 12, direction: "ltr", textAlign: "left" }}
          />
          <Button className="w-full mt-3" onClick={handleCopy}>{copied ? "تم النسخ ✓" : "نسخ النص"}</Button>
        </Modal>
      )}

      {showImport && (
        <Modal title="استيراد نسخة احتياطية" onClose={() => { setShowImport(false); setConfirmingImport(false); setImportError(""); setImportSuccess(false); }}>
          <p className="font-body text-sm mb-3" style={{ color: COLORS.brick }}>
            تحذير: هذا سيستبدل كل البيانات الحالية في البرنامج بالبيانات الموجودة في النص اللي هتلصقه، ولا يمكن التراجع.
          </p>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder="الصق نص النسخة الاحتياطية هنا"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck="false"
            style={{ ...inputStyle(), minHeight: 180, fontFamily: "monospace", fontSize: 12, direction: "ltr", textAlign: "left" }}
          />
          {importError && <p className="font-body text-sm mt-2" style={{ color: COLORS.brick }}>{importError}</p>}
          {importSuccess && <p className="font-body text-sm mt-2 font-bold" style={{ color: COLORS.ledgerLight }}>تم الاستيراد بنجاح ✓</p>}
          {!confirmingImport ? (
            <Button className="w-full mt-3" variant="danger" onClick={() => setConfirmingImport(true)} disabled={!importText.trim() || importBusy}>
              استيراد واستبدال البيانات
            </Button>
          ) : (
            <div className="mt-3">
              <p className="font-body text-xs mb-2 text-center" style={{ color: COLORS.brick }}>متأكد؟ هذا سيمسح البيانات الحالية نهائيًا.</p>
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmingImport(false)}
                  disabled={importBusy}
                  className="font-body text-sm px-4 py-2 rounded-lg disabled:opacity-50"
                  style={{ color: COLORS.inkSoft, background: COLORS.paperAlt }}
                >
                  إلغاء
                </button>
                <button
                  type="button"
                  onClick={handleImport}
                  disabled={importBusy}
                  className="font-body text-sm px-4 py-2 rounded-lg font-bold flex items-center gap-1.5 disabled:opacity-50"
                  style={{ color: "#fff", background: COLORS.brick }}
                >
                  {importBusy && <Loader2 size={14} className="animate-spin" />}
                  {importBusy ? "جارٍ الاستيراد..." : "نعم، استيراد الآن"}
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function UsersView({ users, currentUser, onToggleRole, onDelete, customers, customerTx, treasury, onImportBackup }) {
  const adminCount = users.filter((u) => u.role === "admin").length;
  return (
    <div>
      <TopBar title="المستخدمون" />
      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
          {users.map((u) => {
            const isSelf = u.id === currentUser.id;
            const isAdminUser = u.role === "admin";
            const lastAdmin = isAdminUser && adminCount <= 1;
            return (
              <div key={u.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center font-display font-bold"
                    style={{ background: COLORS.paperAlt, color: COLORS.ledger }}
                  >
                    {u.name.charAt(0)}
                  </div>
                  <div>
                    <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>
                      {u.name} {isSelf && <span className="font-normal" style={{ color: COLORS.inkSoft }}>(أنت)</span>}
                    </p>
                    <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>@{u.username}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="font-body text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1"
                    style={{
                      background: isAdminUser ? "rgba(180,136,58,0.15)" : COLORS.paperAlt,
                      color: isAdminUser ? COLORS.gold : COLORS.inkSoft,
                    }}
                  >
                    {isAdminUser ? <ShieldCheck size={13} /> : <UserCog size={13} />}
                    {isAdminUser ? "مسؤول" : "موظف"}
                  </span>
                  <button
                    onClick={() => onToggleRole(u.id)}
                    disabled={lastAdmin}
                    title={lastAdmin ? "لا يمكن التنازل عن آخر صلاحية مسؤول" : ""}
                    className="p-1.5 rounded-lg hover:opacity-70 disabled:opacity-30"
                    style={{ color: COLORS.ledger }}
                  >
                    {isAdminUser ? <ShieldOff size={15} /> : <ShieldCheck size={15} />}
                  </button>
                  {!isSelf && (
                    <button onClick={() => onDelete(u.id)} className="p-1.5 rounded-lg hover:opacity-70" style={{ color: COLORS.brick }}>
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <p className="font-body text-xs mt-4" style={{ color: COLORS.inkSoft }}>
        المسؤول يمكنه حذف الموردين والدفعات والمصاريف وإدارة صلاحيات المستخدمين. الموظف يمكنه الإضافة والتعديل فقط.
      </p>
      <BackupSection
        users={users}
        customers={customers}
        customerTx={customerTx}
        treasury={treasury}
        onImport={onImportBackup}
      />
    </div>
  );
}

/* ---------------------------------- Root App ---------------------------------- */

export default function App() {
  const [authScreen, setAuthScreen] = useState("login");
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [authError, setAuthError] = useState("");

  const [users, setUsers] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [customerTx, setCustomerTx] = useState([]);
  const [treasury, setTreasury] = useState([]);

  const [tab, setTab] = useState("dashboard");
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const isDesktop = useIsDesktop();
  const [storageOk, setStorageOk] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    const withTimeout = (promise, ms = 30000) =>
      Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms)),
      ]);

    try {
      const [u, c, ct, tr, session] = await withTimeout(
        Promise.all([
          storageGet(KEYS.users, true),
          storageGet(KEYS.customers, true),
          storageGet(KEYS.customerTransactions, true),
          storageGet(KEYS.treasury, true),
          storageGet(KEYS.session, false),
        ])
      );
      const loadedUsers = u || [];
      setUsers(loadedUsers);
      setCustomers(c || []);
      setCustomerTx(ct || []);
      setTreasury(tr || []);
      if (session?.userId) {
        const savedUser = loadedUsers.find((usr) => usr.id === session.userId);
        if (savedUser) setCurrentUser(savedUser);
      }
      setStorageOk(true);
    } catch {
      setStorageOk(false);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleRegister = async (user) => {
    setBusy(true);
    setAuthError("");
    // re-fetch the latest list first, in case another person registered at the same moment
    const latest = (await storageGet(KEYS.users, true)) || users;
    if (latest.some((u) => u.username === user.username)) {
      setBusy(false);
      setAuthError("اسم المستخدم موجود بالفعل، اختر اسماً آخر");
      setUsers(latest);
      return;
    }
    const role = latest.length === 0 ? "admin" : "employee";
    const fullUser = { ...user, role };
    const next = [...latest, fullUser];
    const ok = await storageSet(KEYS.users, next, true);
    setBusy(false);
    if (ok) {
      setUsers(next);
      setCurrentUser(fullUser);
      storageSet(KEYS.session, { userId: fullUser.id }, false);
    } else {
      setAuthError("تعذّر حفظ الحساب، تأكد من اتصالك بالإنترنت وحاول مرة أخرى");
    }
  };

  const toggleUserRole = async (id) => {
    const target = users.find((u) => u.id === id);
    if (!target) return;
    const adminCount = users.filter((u) => u.role === "admin").length;
    if (target.role === "admin" && adminCount <= 1) return;
    const next = users.map((u) => (u.id === id ? { ...u, role: u.role === "admin" ? "employee" : "admin" } : u));
    setUsers(next);
    await storageSet(KEYS.users, next, true);
  };

  const deleteUser = async (id) => {
    if (id === currentUser.id) return;
    const target = users.find((u) => u.id === id);
    const adminCount = users.filter((u) => u.role === "admin").length;
    if (target?.role === "admin" && adminCount <= 1) return;
    if (!confirm(`هل تريد حذف حساب "${target?.name}"؟`)) return;
    const next = users.filter((u) => u.id !== id);
    setUsers(next);
    await storageSet(KEYS.users, next, true);
  };

  const handleLogin = (user) => {
    setCurrentUser(user);
    storageSet(KEYS.session, { userId: user.id }, false);
  };
  const handleLogout = () => {
    setCurrentUser(null);
    setTab("dashboard");
    setSelectedCustomerId(null);
    storageDelete(KEYS.session, false);
  };

  const handleResetAll = async () => {
    await Promise.all([
      storageDelete(KEYS.users, true),
      storageDelete(KEYS.customers, true),
      storageDelete(KEYS.customerTransactions, true),
      storageDelete(KEYS.treasury, true),
      storageDelete(KEYS.session, false),
    ]);
    setUsers([]);
    setCustomers([]);
    setCustomerTx([]);
    setTreasury([]);
    setAuthScreen("register");
  };

  const handleImportBackup = async (data) => {
    const hasAnyRecognizedKey = ["users", "customers", "customerTx", "treasury"].some((k) => Array.isArray(data?.[k]));
    if (!hasAnyRecognizedKey) {
      if (Array.isArray(data?.suppliers) || Array.isArray(data?.transactions) || Array.isArray(data?.expenses)) {
        throw new Error("هذه نسخة احتياطية من إصدار قديم من البرنامج (كانت باسم 'الموردين') ولا يمكن استيرادها في هذا الإصدار الجديد.");
      }
      throw new Error("النص المُدخل لا يحتوي على بيانات نسخة احتياطية معروفة.");
    }

    const newUsers = Array.isArray(data.users) ? data.users : [];
    const newCustomers = Array.isArray(data.customers) ? data.customers : [];
    const newCustomerTx = Array.isArray(data.customerTx) ? data.customerTx : [];
    const newTreasury = Array.isArray(data.treasury) ? data.treasury : [];

    const results = await Promise.all([
      storageSet(KEYS.users, newUsers, true),
      storageSet(KEYS.customers, newCustomers, true),
      storageSet(KEYS.customerTransactions, newCustomerTx, true),
      storageSet(KEYS.treasury, newTreasury, true),
    ]);
    if (results.some((ok) => !ok)) {
      throw new Error("تعذّر حفظ البيانات المستوردة. تأكد من اتصالك بالإنترنت وحاول مرة أخرى.");
    }

    setUsers(newUsers);
    setCustomers(newCustomers);
    setCustomerTx(newCustomerTx);
    setTreasury(newTreasury);
  };

  const addCustomer = async (cust) => {
    const full = { ...cust, createdBy: currentUser.username };
    const next = [...customers, full];
    setCustomers(next);
    await storageSet(KEYS.customers, next, true);
  };
  const editCustomer = async (updated) => {
    const next = customers.map((c) => (c.id === updated.id ? updated : c));
    setCustomers(next);
    await storageSet(KEYS.customers, next, true);
  };
  const deleteCustomer = async (id) => {
    if (currentUser.role !== "admin") return;
    if (!confirm("هل تريد حذف هذا العميل؟ سيتم حذف جميع حركاته المرتبطة به.")) return;
    const next = customers.filter((c) => c.id !== id);
    const nextTx = customerTx.filter((t) => t.customerId !== id);
    setCustomers(next);
    setCustomerTx(nextTx);
    await Promise.all([storageSet(KEYS.customers, next, true), storageSet(KEYS.customerTransactions, nextTx, true)]);
  };

  // Customer transactions are completely independent from the treasury by design -
  // no auto-sync in either direction.
  const addCustomerTx = async (tx) => {
    const full = { ...tx, createdBy: currentUser.username };
    const next = [...customerTx, full];
    setCustomerTx(next);
    await storageSet(KEYS.customerTransactions, next, true);
  };
  const editCustomerTx = async (updated) => {
    const next = customerTx.map((t) => (t.id === updated.id ? { ...t, ...updated } : t));
    setCustomerTx(next);
    await storageSet(KEYS.customerTransactions, next, true);
  };
  const deleteCustomerTx = async (id) => {
    if (currentUser.role !== "admin") return;
    const next = customerTx.filter((t) => t.id !== id);
    setCustomerTx(next);
    await storageSet(KEYS.customerTransactions, next, true);
  };

  const addTreasuryEntry = async (entry) => {
    const full = { ...entry, createdBy: currentUser.username };
    const next = [...treasury, full];
    setTreasury(next);
    await storageSet(KEYS.treasury, next, true);
  };
  const deleteTreasuryEntry = async (id) => {
    if (currentUser.role !== "admin") return;
    const next = treasury.filter((t) => t.id !== id);
    setTreasury(next);
    await storageSet(KEYS.treasury, next, true);
  };

  const isAdmin = currentUser?.role === "admin";

  const visibleCustomers = useMemo(
    () => (isAdmin ? customers : customers.filter((c) => c.createdBy === currentUser?.username)),
    [customers, isAdmin, currentUser]
  );
  const visibleCustomerTx = useMemo(
    () => (isAdmin ? customerTx : customerTx.filter((t) => t.createdBy === currentUser?.username)),
    [customerTx, isAdmin, currentUser]
  );
  const visibleTreasury = useMemo(
    () => (isAdmin ? treasury : treasury.filter((t) => t.createdBy === currentUser?.username)),
    [treasury, isAdmin, currentUser]
  );
  const visibleSelectedCustomer = useMemo(
    () => visibleCustomers.find((c) => c.id === selectedCustomerId) || null,
    [visibleCustomers, selectedCustomerId]
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: COLORS.paper }}>
                <Loader2 size={28} className="animate-spin" color={COLORS.ledger} />
      </div>
    );
  }

  if (!storageOk) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: COLORS.paper }} dir="rtl">
                <div className="w-full max-w-sm rounded-2xl p-6 text-center" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-4" style={{ background: COLORS.brickSoft }}>
            <AlertCircle size={24} color={COLORS.brick} />
          </div>
          <h2 className="font-display text-lg font-bold mb-2" style={{ color: COLORS.ledger }}>تعذّر الوصول إلى بيانات البرنامج</h2>
          <p className="font-body text-sm mb-5" style={{ color: COLORS.inkSoft }}>
            لازم توافق على إذن "الوصول للبيانات المشتركة" اللي بيظهر عند فتح البرنامج عشان يقدر يحفظ ويقرأ البيانات. لو ظهر لك إذن ولم توافق عليه (Allow)، أو لو الاتصال بطيء جدًا، أغلق البرنامج بالكامل وافتحه من جديد ووافق على الإذن فور ظهوره.
          </p>
          <Button className="w-full" onClick={loadAll}>إعادة المحاولة</Button>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="font-body">
                {authScreen === "login" ? (
          <LoginScreen onLogin={handleLogin} goRegister={() => { setAuthScreen("register"); setAuthError(""); }} users={users} loading={busy} onResetAll={handleResetAll} />
        ) : (
          <RegisterScreen onRegister={handleRegister} goLogin={() => { setAuthScreen("login"); setAuthError(""); }} users={users} loading={busy} serverError={authError} />
        )}
      </div>
    );
  }

  const activeTab = visibleSelectedCustomer ? "customers" : tab;

  return (
    <div className="font-body" style={{ display: "flex", flexDirection: isDesktop ? "row" : "column", minHeight: "100vh", background: COLORS.paper }} dir="rtl">
            {!isDesktop && <MobileTopBar onOpenMenu={() => setMobileNavOpen(true)} tab={activeTab} />}
      {mobileNavOpen && !isDesktop && (
        <div
          className="no-print"
          style={{ position: "fixed", inset: 0, zIndex: 30, background: "rgba(30,42,34,0.55)" }}
          onClick={() => setMobileNavOpen(false)}
        />
      )}
      <Sidebar
        tab={activeTab}
        setTab={(t) => { setTab(t); setSelectedCustomerId(null); setMobileNavOpen(false); }}
        currentUser={currentUser}
        onLogout={handleLogout}
        mobileOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        isDesktop={isDesktop}
      />
      <div style={{ flex: 1, minWidth: 0, width: "100%", maxWidth: 1152, padding: isDesktop ? 32 : 16 }}>
        {visibleSelectedCustomer ? (
          <CustomerDetail
            customer={visibleSelectedCustomer}
            customerTx={visibleCustomerTx}
            onBack={() => setSelectedCustomerId(null)}
            onAddTx={addCustomerTx}
            onEditTx={editCustomerTx}
            onDeleteTx={deleteCustomerTx}
            onEdit={editCustomer}
            isAdmin={isAdmin}
          />
        ) : tab === "dashboard" ? (
          <Dashboard customers={visibleCustomers} customerTx={visibleCustomerTx} treasury={visibleTreasury} isAdmin={isAdmin} />
        ) : tab === "customers" ? (
          <CustomersView
            customers={visibleCustomers}
            customerTx={visibleCustomerTx}
            onAdd={addCustomer}
            onEdit={editCustomer}
            onDelete={deleteCustomer}
            onOpen={setSelectedCustomerId}
            isAdmin={isAdmin}
          />
        ) : tab === "treasury" ? (
          <TreasuryView treasury={visibleTreasury} onAdd={addTreasuryEntry} onDelete={deleteTreasuryEntry} isAdmin={isAdmin} />
        ) : tab === "users" && isAdmin ? (
          <UsersView
            users={users}
            currentUser={currentUser}
            onToggleRole={toggleUserRole}
            onDelete={deleteUser}
            customers={customers}
            customerTx={customerTx}
            treasury={treasury}
            onImportBackup={handleImportBackup}
          />
        ) : (
          <ReportsView customers={visibleCustomers} customerTx={visibleCustomerTx} treasury={visibleTreasury} isAdmin={isAdmin} />
        )}
      </div>
    </div>
  );
}
