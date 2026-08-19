import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  LogIn, UserPlus, LogOut, Plus, X, Trash2, ArrowDownLeft, ArrowUpRight,
  Wallet, Users, Receipt, BarChart3, LayoutGrid, Search, ChevronRight, Loader2, AlertCircle,
  Pencil, Download, ShieldCheck, ShieldOff, UserCog, Menu, Landmark, Coins, Banknote
} from "lucide-react";
import * as db from "./lib/db";
import { hashPassword, verifyPassword } from "./lib/crypto";

/* ---------------------------------------------------------
   بياع الحلويين — Ledger
   Design language: an accountant's ledger book, restyled with
   the brand's hot-pink / black / white palette.
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

// Served from /public/logo.png (see vite.config.js / index.html for PWA icons).
const LOGO_SRC = "/logo.png";

const SESSION_KEY = "sweets_vendor_session_user_id";

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

/* Reliable viewport detection via JS, matching the original artifact's
   approach (works everywhere, no dependency on CSS breakpoints loading). */
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

function LoginScreen({ onLogin, goRegister, loading, error, onResetAll }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmingReset, setConfirmingReset] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    onLogin(username.trim(), password);
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
    onRegister({ name: name.trim(), username: username.trim(), password: password.trim() });
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
    { key: "suppliers", label: "الموردون", icon: Users },
    { key: "expenses", label: "المصاريف", icon: Receipt },
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
  const titles = { dashboard: "لوحة التحكم", suppliers: "الموردون", expenses: "المصاريف", treasury: "الخزينة", reports: "التقارير", users: "المستخدمون" };
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

function Dashboard({ suppliers, transactions, expenses, isAdmin }) {
  const totalPaid = transactions.filter((t) => t.type === "to").reduce((s, t) => s + Number(t.amount), 0);
  const totalReceived = transactions.filter((t) => t.type === "from").reduce((s, t) => s + Number(t.amount), 0);
  const totalExpenses = expenses.reduce((s, e) => s + Number(e.amount), 0);
  const recent = [...transactions].sort((a, b) => b.createdAt - a.createdAt).slice(0, 6);

  return (
    <div>
      <TopBar title="لوحة التحكم" />
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          هذه البيانات تعرض فقط ما أضفته أنت. المسؤول يمكنه رؤية بيانات جميع المستخدمين.
        </p>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <StatCard icon={Users} label="عدد الموردين" value={suppliers.length} color={COLORS.ledger} />
        <StatCard icon={ArrowUpRight} label="إجمالي المدفوع للموردين" value={totalPaid} color={COLORS.brick} />
        <StatCard icon={ArrowDownLeft} label="إجمالي المستلم من الموردين" value={totalReceived} color={COLORS.ledgerLight} />
        <StatCard icon={Receipt} label="إجمالي المصاريف" value={totalExpenses} color={COLORS.gold} />
      </div>
      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-3" style={{ color: COLORS.ink }}>آخر الحركات</h3>
        {recent.length === 0 ? (
          <EmptyState icon={Receipt} title="لا توجد حركات بعد" subtitle="ابدأ بإضافة مورد ثم سجّل أول دفعة" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {recent.map((t) => {
              const s = suppliers.find((sp) => sp.id === t.supplierId);
              return (
                <div key={t.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-full" style={{ background: t.type === "to" ? COLORS.brickSoft : "rgba(47,107,87,0.12)" }}>
                      {t.type === "to" ? <ArrowUpRight size={15} color={COLORS.brick} /> : <ArrowDownLeft size={15} color={COLORS.ledgerLight} />}
                    </div>
                    <div>
                      <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>{s ? s.name : "مورد محذوف"}</p>
                      <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{t.type === "to" ? "دفع" : "استلم"} · {t.date}</p>
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

/* ---------------------------------- Suppliers ---------------------------------- */

function SupplierFormModal({ onClose, onSave, initial }) {
  const isEdit = Boolean(initial);
  const [name, setName] = useState(initial?.name || "");
  const [phone, setPhone] = useState(initial?.phone || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  return (
    <Modal title={isEdit ? "تعديل بيانات المورد" : "إضافة مورد جديد"} onClose={onClose}>
      <Field label="اسم المورد">
        <input style={inputStyle()} value={name} onChange={(e) => setName(e.target.value)} placeholder="مثال: شركة النور للتوريدات" />
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
        {isEdit ? <Pencil size={18} /> : <Plus size={18} />} {isEdit ? "حفظ التعديلات" : "حفظ المورد"}
      </Button>
    </Modal>
  );
}

function SuppliersView({ suppliers, transactions, onAdd, onEdit, onDelete, onOpen, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [query, setQuery] = useState("");

  const balanceOf = (id) => {
    const list = transactions.filter((t) => t.supplierId === id);
    const paid = list.filter((t) => t.type === "to").reduce((s, t) => s + Number(t.amount), 0);
    const received = list.filter((t) => t.type === "from").reduce((s, t) => s + Number(t.amount), 0);
    return received - paid;
  };

  const filtered = suppliers.filter((s) => s.name.includes(query) || (s.phone || "").includes(query));

  return (
    <div>
      <TopBar
        title="الموردون"
        action={<Button onClick={() => setShowAdd(true)}><Plus size={16} /> مورد جديد</Button>}
      />
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          تظهر هنا فقط الموردون الذين أضفتهم أنت.
        </p>
      )}
      <div className="relative mb-4 max-w-sm">
        <Search size={16} className="absolute top-1/2 -translate-y-1/2 right-3" color={COLORS.inkSoft} />
        <input style={{ ...inputStyle(), paddingRight: 34 }} placeholder="بحث عن مورد..." value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={Users} title="لا يوجد موردون" subtitle="أضف أول مورد لبدء تسجيل دفعاته" />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((s) => {
            const bal = balanceOf(s.id);
            return (
              <div
                key={s.id}
                onClick={() => onOpen(s.id)}
                className="rounded-2xl p-5 cursor-pointer hover:shadow-md transition-shadow"
                style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center font-display font-bold" style={{ background: COLORS.paperAlt, color: COLORS.ledger }}>
                    {s.name.charAt(0)}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditing(s); }}
                      className="p-1.5 rounded-lg hover:opacity-70"
                      style={{ color: COLORS.inkSoft }}
                    >
                      <Pencil size={15} />
                    </button>
                    {isAdmin && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                        className="p-1.5 rounded-lg hover:opacity-70"
                        style={{ color: COLORS.brick }}
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>
                </div>
                <p className="font-body font-bold mb-1" style={{ color: COLORS.ink }}>{s.name}</p>
                {s.phone && <p className="font-body text-xs mb-3" style={{ color: COLORS.inkSoft }}>{s.phone}</p>}
                <LedgerRow
                  label="الرصيد الصافي"
                  value={fmt(Math.abs(bal))}
                  bold
                  color={bal > 0 ? COLORS.ledgerLight : bal < 0 ? COLORS.brick : COLORS.inkSoft}
                />
                <p className="font-body text-xs mt-1" style={{ color: COLORS.inkSoft }}>
                  {bal > 0 ? "لنا في ذمته" : bal < 0 ? "له في ذمتنا" : "متوازن"}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {showAdd && (
        <SupplierFormModal
          onClose={() => setShowAdd(false)}
          onSave={(sup) => { onAdd(sup); setShowAdd(false); }}
        />
      )}
      {editing && (
        <SupplierFormModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={(sup) => { onEdit(sup); setEditing(null); }}
        />
      )}
    </div>
  );
}

/* ---------------------------------- Supplier detail ---------------------------------- */

function TransactionFormModal({ onClose, onSave, initial }) {
  const isEdit = Boolean(initial);
  const [type, setType] = useState(initial?.type || "to");
  const [amount, setAmount] = useState(initial ? String(initial.amount) : "");
  const [date, setDate] = useState(initial?.date || todayStr());
  const [note, setNote] = useState(initial?.note || "");

  return (
    <Modal title={isEdit ? "تعديل حركة نقدية" : "إضافة حركة نقدية"} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 mb-4">
        <button
          onClick={() => setType("to")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "to" ? COLORS.brick : COLORS.paperAlt, color: type === "to" ? "#fff" : COLORS.inkSoft }}
        >
          <ArrowUpRight size={15} /> دفع
        </button>
        <button
          onClick={() => setType("from")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "from" ? COLORS.ledgerLight : COLORS.paperAlt, color: type === "from" ? "#fff" : COLORS.inkSoft }}
        >
          <ArrowDownLeft size={15} /> استلم
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
        variant={type === "to" ? "danger" : "primary"}
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

function SupplierDetail({ supplier, transactions, onBack, onAddTx, onEditTx, onDeleteTx, onEdit, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editingTx, setEditingTx] = useState(null);
  const list = transactions.filter((t) => t.supplierId === supplier.id).sort((a, b) => b.createdAt - a.createdAt);
  const paid = list.filter((t) => t.type === "to").reduce((s, t) => s + Number(t.amount), 0);
  const received = list.filter((t) => t.type === "from").reduce((s, t) => s + Number(t.amount), 0);
  const balance = received - paid;

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1 font-body text-sm font-semibold mb-4 no-print" style={{ color: COLORS.inkSoft }}>
        <ChevronRight size={16} /> رجوع إلى الموردين
      </button>
      <TopBar
        title={supplier.name}
        action={
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => setShowEdit(true)}><Pencil size={16} /> تعديل</Button>
            <Button onClick={() => setShowAdd(true)}><Plus size={16} /> إضافة حركة نقدية</Button>
          </div>
        }
      />
      {supplier.phone && <p className="font-body text-sm -mt-4 mb-6" style={{ color: COLORS.inkSoft }}>{supplier.phone}</p>}

      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="إجمالي ما تم دفعه" value={fmt(paid)} color={COLORS.brick} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="إجمالي المسلم له" value={fmt(received)} color={COLORS.ledgerLight} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.ledgerDark }}>
          <p className="font-body text-sm mb-1" style={{ color: "rgba(246,243,234,0.7)" }}>الرصيد الصافي</p>
          <p className="tabular font-display text-2xl font-bold" style={{ color: COLORS.goldSoft }}>{fmt(Math.abs(balance))}</p>
          <p className="font-body text-xs mt-1" style={{ color: "rgba(246,243,234,0.6)" }}>
            {balance > 0 ? "لنا في ذمته" : balance < 0 ? "له في ذمتنا" : "متوازن"}
          </p>
        </div>
      </div>

      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-3" style={{ color: COLORS.ink }}>سجل الحركات النقدية</h3>
        {list.length === 0 ? (
          <EmptyState icon={Wallet} title="لا توجد حركات مسجلة" subtitle="أضف أول حركة نقدية لهذا المورد" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {list.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full" style={{ background: t.type === "to" ? COLORS.brickSoft : "rgba(47,107,87,0.12)" }}>
                    {t.type === "to" ? <ArrowUpRight size={15} color={COLORS.brick} /> : <ArrowDownLeft size={15} color={COLORS.ledgerLight} />}
                  </div>
                  <div>
                    <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>{t.type === "to" ? "دفع" : "استلم"}</p>
                    <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{t.date}{t.note ? ` · ${t.note}` : ""}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="tabular font-body font-bold" style={{ color: t.type === "to" ? COLORS.brick : COLORS.ledgerLight }}>{fmt(t.amount)}</span>
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
        <TransactionFormModal
          onClose={() => setShowAdd(false)}
          onSave={(tx) => { onAddTx({ ...tx, supplierId: supplier.id }); setShowAdd(false); }}
        />
      )}
      {editingTx && (
        <TransactionFormModal
          initial={editingTx}
          onClose={() => setEditingTx(null)}
          onSave={(tx) => { onEditTx(tx); setEditingTx(null); }}
        />
      )}
      {showEdit && (
        <SupplierFormModal
          initial={supplier}
          onClose={() => setShowEdit(false)}
          onSave={(sup) => { onEdit(sup); setShowEdit(false); }}
        />
      )}
    </div>
  );
}

/* ---------------------------------- Expenses ---------------------------------- */

function AddExpenseModal({ onClose, onSave }) {
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("عام");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayStr());
  const categories = ["عام", "إيجار", "رواتب", "مواصلات", "صيانة", "فواتير", "أخرى"];

  return (
    <Modal title="إضافة مصروف" onClose={onClose}>
      <Field label="الوصف">
        <input style={inputStyle()} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="مثال: فاتورة كهرباء" />
      </Field>
      <Field label="التصنيف">
        <select style={inputStyle()} value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </Field>
      <Field label="المبلغ">
        <input style={inputStyle()} type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
      </Field>
      <Field label="التاريخ">
        <input style={inputStyle()} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </Field>
      <Button
        className="w-full"
        variant="gold"
        onClick={() => description.trim() && Number(amount) > 0 && onSave({ id: genId(), description: description.trim(), category, amount: Number(amount), date, createdAt: Date.now() })}
      >
        <Plus size={18} /> حفظ المصروف
      </Button>
    </Modal>
  );
}

function ExpensesView({ expenses, onAdd, onDelete, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const total = expenses.reduce((s, e) => s + Number(e.amount), 0);
  const sorted = [...expenses].sort((a, b) => b.createdAt - a.createdAt);

  return (
    <div>
      <TopBar title="المصاريف" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} /> مصروف جديد</Button>} />
      {!isAdmin && (
        <p className="font-body text-sm mb-4 px-4 py-2.5 rounded-lg inline-block" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
          تظهر هنا فقط المصاريف التي أضفتها أنت.
        </p>
      )}
      <div className="rounded-2xl p-5 mb-6 max-w-xs" style={{ background: COLORS.ledgerDark }}>
        <p className="font-body text-sm mb-1" style={{ color: "rgba(246,243,234,0.7)" }}>إجمالي المصاريف</p>
        <p className="tabular font-display text-2xl font-bold" style={{ color: COLORS.goldSoft }}>{fmt(total)}</p>
      </div>

      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        {sorted.length === 0 ? (
          <EmptyState icon={Receipt} title="لا توجد مصاريف مسجلة" subtitle="أضف أول مصروف لتتبع نفقاتك" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {sorted.map((e) => (
              <div key={e.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-body text-sm font-bold" style={{ color: COLORS.ink }}>{e.description}</p>
                  <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{e.category} · {e.date}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="tabular font-body font-bold" style={{ color: COLORS.brick }}>{fmt(e.amount)}</span>
                  {isAdmin && (
                    <button onClick={() => onDelete(e.id)} className="p-1 rounded hover:opacity-70 no-print" style={{ color: COLORS.inkSoft }}>
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
        <AddExpenseModal onClose={() => setShowAdd(false)} onSave={(e) => { onAdd(e); setShowAdd(false); }} />
      )}
    </div>
  );
}

/* ---------------------------------- Treasury (رأس المال / السيولة النقدية / صافي الخزينة) ---------------------------------- */

function AddTreasuryModal({ onClose, onSave }) {
  const [type, setType] = useState("capital");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayStr());
  const [note, setNote] = useState("");

  return (
    <Modal title="إضافة إلى الخزينة" onClose={onClose}>
      <div className="grid grid-cols-2 gap-2 mb-4">
        <button
          onClick={() => setType("capital")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "capital" ? COLORS.gold : COLORS.paperAlt, color: type === "capital" ? "#fff" : COLORS.inkSoft }}
        >
          <Coins size={15} /> رأس مال أساسي
        </button>
        <button
          onClick={() => setType("cash")}
          className="rounded-lg py-2.5 font-body font-bold text-sm flex items-center justify-center gap-1.5"
          style={{ background: type === "cash" ? COLORS.ledgerLight : COLORS.paperAlt, color: type === "cash" ? "#fff" : COLORS.inkSoft }}
        >
          <Banknote size={15} /> سيولة نقدية
        </button>
      </div>
      <Field label="المبلغ">
        <input style={inputStyle()} type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
      </Field>
      <Field label="التاريخ">
        <input style={inputStyle()} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </Field>
      <Field label="ملاحظة (اختياري)">
        <input style={inputStyle()} value={note} onChange={(e) => setNote(e.target.value)} placeholder="مصدر المبلغ" />
      </Field>
      <Button
        className="w-full"
        variant={type === "capital" ? "gold" : "primary"}
        onClick={() => Number(amount) > 0 && onSave({ id: genId(), type, amount: Number(amount), date, note: note.trim(), createdAt: Date.now() })}
      >
        <Plus size={18} /> حفظ
      </Button>
    </Modal>
  );
}

function TreasuryView({ treasury, expenses, onAdd, onDelete, isAdmin }) {
  const [showAdd, setShowAdd] = useState(false);
  const totalCapital = treasury.filter((t) => t.type === "capital").reduce((s, t) => s + Number(t.amount), 0);
  const totalCash = treasury.filter((t) => t.type === "cash").reduce((s, t) => s + Number(t.amount), 0);
  const totalExpenses = expenses.reduce((s, e) => s + Number(e.amount), 0);
  const net = totalCapital + totalCash - totalExpenses;
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
          <LedgerRow label="رأس المال الأساسي" value={fmt(totalCapital)} color={COLORS.gold} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <LedgerRow label="السيولة النقدية" value={fmt(totalCash)} color={COLORS.ledgerLight} bold />
        </div>
        <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.ledgerDark }}>
          <p className="font-body text-sm mb-1" style={{ color: "rgba(246,243,234,0.7)" }}>صافي الخزينة</p>
          <p className="tabular font-display text-xl sm:text-2xl font-bold" style={{ color: net >= 0 ? COLORS.goldSoft : COLORS.brickSoft }}>{fmt(Math.abs(net))}</p>
          {net < 0 && <p className="font-body text-xs mt-1" style={{ color: "rgba(246,243,234,0.6)" }}>عجز في الخزينة</p>}
        </div>
      </div>

      <div className="rounded-2xl p-4 sm:p-5" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
        <h3 className="font-body font-bold mb-3" style={{ color: COLORS.ink }}>سجل الخزينة</h3>
        {sorted.length === 0 ? (
          <EmptyState icon={Landmark} title="لا توجد إيداعات مسجلة" subtitle="أضف رأس المال الأساسي أو سيولة نقدية" />
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: COLORS.line }}>
            {sorted.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full" style={{ background: t.type === "capital" ? "rgba(180,136,58,0.15)" : "rgba(47,107,87,0.12)" }}>
                    {t.type === "capital" ? <Coins size={15} color={COLORS.gold} /> : <Banknote size={15} color={COLORS.ledgerLight} />}
                  </div>
                  <div>
                    <p className="font-body text-sm font-bold flex items-center gap-1.5" style={{ color: COLORS.ink }}>
                      {t.type === "capital" ? "رأس مال أساسي" : "سيولة نقدية"}
                      {t.sourceTransactionId && (
                        <span className="font-body text-[10px] font-normal px-1.5 py-0.5 rounded-full" style={{ background: COLORS.paperAlt, color: COLORS.inkSoft }}>
                          مرتبط تلقائيًا
                        </span>
                      )}
                    </p>
                    <p className="font-body text-xs" style={{ color: COLORS.inkSoft }}>{t.date}{t.note ? ` · ${t.note}` : ""}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="tabular font-body font-bold" style={{ color: t.type === "capital" ? COLORS.gold : COLORS.ledgerLight }}>{fmt(t.amount)}</span>
                  {isAdmin && !t.sourceTransactionId && (
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
          صافي الخزينة = رأس المال الأساسي + السيولة النقدية − إجمالي المصاريف المسجّلة. القيود الموسومة بـ"مرتبط تلقائيًا" منسوخة من حركات "دفع" مع الموردين، وتتحدّث أو تُحذف تلقائيًا لو عدّلت أو حذفت الحركة الأصلية من صفحة المورد.
        </p>
      </div>

      {showAdd && (
        <AddTreasuryModal onClose={() => setShowAdd(false)} onSave={(t) => { onAdd(t); setShowAdd(false); }} />
      )}
    </div>
  );
}

/* ---------------------------------- Reports ---------------------------------- */

function ReportsView({ suppliers, transactions, expenses, isAdmin }) {
  const totalPaid = transactions.filter((t) => t.type === "to").reduce((s, t) => s + Number(t.amount), 0);
  const totalReceived = transactions.filter((t) => t.type === "from").reduce((s, t) => s + Number(t.amount), 0);
  const totalExpenses = expenses.reduce((s, e) => s + Number(e.amount), 0);

  const bySupplier = suppliers.map((s) => {
    const list = transactions.filter((t) => t.supplierId === s.id);
    const paid = list.filter((t) => t.type === "to").reduce((sum, t) => sum + Number(t.amount), 0);
    const received = list.filter((t) => t.type === "from").reduce((sum, t) => sum + Number(t.amount), 0);
    return { name: s.name, net: received - paid };
  }).sort((a, b) => Math.abs(b.net) - Math.abs(a.net));

  const maxAbs = Math.max(1, ...bySupplier.map((s) => Math.abs(s.net)));

  const byCategory = {};
  expenses.forEach((e) => { byCategory[e.category] = (byCategory[e.category] || 0) + Number(e.amount); });
  const catList = Object.entries(byCategory).sort((a, b) => b[1] - a[1]);
  const maxCat = Math.max(1, ...catList.map(([, v]) => v));

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
        <LedgerRow label="إجمالي المدفوع لجميع الموردين" value={fmt(totalPaid)} color={COLORS.brick} bold />
        <LedgerRow label="إجمالي المستلم من جميع الموردين" value={fmt(totalReceived)} color={COLORS.ledgerLight} bold />
        <LedgerRow label="إجمالي المصاريف" value={fmt(totalExpenses)} color={COLORS.gold} bold />
        <div style={{ borderTop: `1px solid ${COLORS.line}`, marginTop: 8, paddingTop: 8 }}>
          <LedgerRow label="صافي الحركة النقدية" value={fmt(totalReceived - totalPaid - totalExpenses)} bold color={COLORS.ledger} />
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="rounded-2xl p-6" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <h3 className="font-body font-bold mb-4" style={{ color: COLORS.ink }}>الرصيد الصافي لكل مورد</h3>
          {bySupplier.length === 0 ? (
            <p className="font-body text-sm" style={{ color: COLORS.inkSoft }}>لا توجد بيانات بعد</p>
          ) : (
            <div className="flex flex-col gap-3">
              {bySupplier.map((s) => (
                <div key={s.name}>
                  <div className="flex justify-between mb-1">
                    <span className="font-body text-sm font-semibold" style={{ color: COLORS.ink }}>{s.name}</span>
                    <span className="tabular font-body text-sm font-bold" style={{ color: s.net >= 0 ? COLORS.ledgerLight : COLORS.brick }}>{fmt(Math.abs(s.net))}</span>
                  </div>
                  <div className="h-2 rounded-full w-full" style={{ background: COLORS.paperAlt }}>
                    <div
                      className="h-2 rounded-full"
                      style={{ width: `${(Math.abs(s.net) / maxAbs) * 100}%`, background: s.net >= 0 ? COLORS.ledgerLight : COLORS.brick }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl p-6" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <h3 className="font-body font-bold mb-4" style={{ color: COLORS.ink }}>المصاريف حسب التصنيف</h3>
          {catList.length === 0 ? (
            <p className="font-body text-sm" style={{ color: COLORS.inkSoft }}>لا توجد مصاريف بعد</p>
          ) : (
            <div className="flex flex-col gap-3">
              {catList.map(([cat, val]) => (
                <div key={cat}>
                  <div className="flex justify-between mb-1">
                    <span className="font-body text-sm font-semibold" style={{ color: COLORS.ink }}>{cat}</span>
                    <span className="tabular font-body text-sm font-bold" style={{ color: COLORS.gold }}>{fmt(val)}</span>
                  </div>
                  <div className="h-2 rounded-full w-full" style={{ background: COLORS.paperAlt }}>
                    <div className="h-2 rounded-full" style={{ width: `${(val / maxCat) * 100}%`, background: COLORS.gold }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------- Users (admin) ---------------------------------- */

function BackupSection({ users, suppliers, transactions, expenses, treasury, onImport }) {
  const [showExport, setShowExport] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState("");
  const [confirmingImport, setConfirmingImport] = useState(false);
  const [copied, setCopied] = useState(false);

  const backupData = () =>
    JSON.stringify({ users, suppliers, transactions, expenses, treasury, exportedAt: new Date().toISOString() }, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(backupData());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked - user can select the text manually */
    }
  };

  const handleImport = () => {
    let parsed;
    try {
      parsed = JSON.parse(importText);
    } catch {
      setImportError("النص غير صالح، تأكد أنك لصقت نص النسخة الاحتياطية كاملاً كما هو");
      return;
    }
    if (!parsed || typeof parsed !== "object") {
      setImportError("النص غير صالح، تأكد أنك لصقت نص النسخة الاحتياطية كاملاً كما هو");
      return;
    }
    setImportError("");
    onImport(parsed);
    setShowImport(false);
    setConfirmingImport(false);
    setImportText("");
  };

  return (
    <div className="rounded-2xl p-4 sm:p-5 mt-6" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
      <h3 className="font-body font-bold mb-2" style={{ color: COLORS.ink }}>النسخ الاحتياطي للبيانات</h3>
      <p className="font-body text-sm mb-4" style={{ color: COLORS.inkSoft }}>
        احفظ نسخة من كل البيانات (الحسابات، الموردين، الدفعات، المصاريف، الخزينة) في مكان آمن عندك، عشان تقدر تسترجعها لو احتجت تفتح نسخة جديدة من البرنامج بعد أي تعديل مستقبلي.
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
        <Modal title="استيراد نسخة احتياطية" onClose={() => { setShowImport(false); setConfirmingImport(false); setImportError(""); }}>
          <p className="font-body text-sm mb-3" style={{ color: COLORS.brick }}>
            تحذير: هذا سيستبدل كل البيانات الحالية في البرنامج بالبيانات الموجودة في النص اللي هتلصقه، ولا يمكن التراجع.
          </p>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder="الصق نص النسخة الاحتياطية هنا"
            style={{ ...inputStyle(), minHeight: 180, fontFamily: "monospace", fontSize: 12, direction: "ltr", textAlign: "left" }}
          />
          {importError && <p className="font-body text-sm mt-2" style={{ color: COLORS.brick }}>{importError}</p>}
          {!confirmingImport ? (
            <Button className="w-full mt-3" variant="danger" onClick={() => setConfirmingImport(true)} disabled={!importText.trim()}>
              استيراد واستبدال البيانات
            </Button>
          ) : (
            <div className="mt-3">
              <p className="font-body text-xs mb-2 text-center" style={{ color: COLORS.brick }}>متأكد؟ هذا سيمسح البيانات الحالية نهائيًا.</p>
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmingImport(false)}
                  className="font-body text-sm px-4 py-2 rounded-lg"
                  style={{ color: COLORS.inkSoft, background: COLORS.paperAlt }}
                >
                  إلغاء
                </button>
                <button
                  type="button"
                  onClick={handleImport}
                  className="font-body text-sm px-4 py-2 rounded-lg font-bold"
                  style={{ color: "#fff", background: COLORS.brick }}
                >
                  نعم، استيراد الآن
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function UsersView({ users, currentUser, onToggleRole, onDelete, suppliers, transactions, expenses, treasury, onImportBackup }) {
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
        suppliers={suppliers}
        transactions={transactions}
        expenses={expenses}
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
  const [loginError, setLoginError] = useState("");
  const [loadError, setLoadError] = useState("");

  const [users, setUsers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [treasury, setTreasury] = useState([]);

  const [tab, setTab] = useState("dashboard");
  const [selectedSupplierId, setSelectedSupplierId] = useState(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const isDesktop = useIsDesktop();

  const loadAll = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [u, s, t, e, tr] = await Promise.all([
        db.listUsers(),
        db.listSuppliers(),
        db.listTransactions(),
        db.listExpenses(),
        db.listTreasury(),
      ]);
      setUsers(u);
      setSuppliers(s);
      setTransactions(t);
      setExpenses(e);
      setTreasury(tr);

      const savedId = localStorage.getItem(SESSION_KEY);
      if (savedId) {
        const savedUser = u.find((usr) => usr.id === savedId);
        if (savedUser) setCurrentUser(savedUser);
      }
    } catch (err) {
      console.error(err);
      setLoadError(
        "تعذّر الاتصال بقاعدة البيانات. تأكد من ضبط متغيرات VITE_SUPABASE_URL و VITE_SUPABASE_ANON_KEY في ملف .env، ومن أنك نفّذت supabase/schema.sql على مشروع Supabase الخاص بك."
      );
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  /* ---------------------------------- auth ---------------------------------- */

  const handleRegister = async (draft) => {
    setBusy(true);
    setAuthError("");
    try {
      const latest = await db.listUsers();
      if (latest.some((u) => u.username === draft.username)) {
        setUsers(latest);
        setAuthError("اسم المستخدم موجود بالفعل، اختر اسماً آخر");
        setBusy(false);
        return;
      }
      const { hash, salt } = await hashPassword(draft.password);
      const role = latest.length === 0 ? "admin" : "employee";
      const created = await db.createUser({
        id: genId(),
        name: draft.name,
        username: draft.username,
        role,
        passwordHash: hash,
        passwordSalt: salt,
        createdAt: Date.now(),
      });
      setUsers([...latest, created]);
      setCurrentUser(created);
      localStorage.setItem(SESSION_KEY, created.id);
    } catch (err) {
      console.error(err);
      setAuthError("تعذّر حفظ الحساب، تأكد من اتصالك بالإنترنت وإعداد قاعدة البيانات وحاول مرة أخرى");
    }
    setBusy(false);
  };

  const handleLogin = async (username, password) => {
    setBusy(true);
    setLoginError("");
    const user = users.find((u) => u.username === username);
    const valid = user ? await verifyPassword(password, user.passwordHash, user.passwordSalt) : false;
    setBusy(false);
    if (!user || !valid) {
      setLoginError("اسم المستخدم أو كلمة المرور غير صحيحة");
      return;
    }
    setCurrentUser(user);
    localStorage.setItem(SESSION_KEY, user.id);
  };

  const handleLogout = () => {
    setCurrentUser(null);
    setTab("dashboard");
    setSelectedSupplierId(null);
    localStorage.removeItem(SESSION_KEY);
  };

  const handleResetAll = async () => {
    setBusy(true);
    try {
      await db.wipeAllData();
      setUsers([]);
      setSuppliers([]);
      setTransactions([]);
      setExpenses([]);
      setTreasury([]);
      localStorage.removeItem(SESSION_KEY);
      setAuthScreen("register");
      setLoginError("");
    } catch (err) {
      console.error(err);
      alert("تعذّر مسح البيانات. تأكد من صلاحيات قاعدة البيانات.");
    }
    setBusy(false);
  };

  const handleImportBackup = async (data) => {
    setBusy(true);
    try {
      await db.wipeAllData();
      const newUsers = Array.isArray(data.users) ? data.users : [];
      const newSuppliers = Array.isArray(data.suppliers) ? data.suppliers : [];
      const newTransactions = Array.isArray(data.transactions) ? data.transactions : [];
      const newExpenses = Array.isArray(data.expenses) ? data.expenses : [];
      const newTreasury = Array.isArray(data.treasury) ? data.treasury : [];

      await db.bulkInsert(
        "users",
        newUsers.map((u) => ({
          id: u.id,
          name: u.name,
          username: u.username,
          role: u.role,
          password_hash: u.passwordHash || u.password_hash || "",
          password_salt: u.passwordSalt || u.password_salt || "",
          created_at: u.createdAt,
        }))
      );
      await db.bulkInsert(
        "suppliers",
        newSuppliers.map((s) => ({ id: s.id, name: s.name, phone: s.phone || "", notes: s.notes || "", created_by: s.createdBy, created_at: s.createdAt }))
      );
      await db.bulkInsert(
        "transactions",
        newTransactions.map((t) => ({ id: t.id, supplier_id: t.supplierId, type: t.type, amount: t.amount, date: t.date, note: t.note || "", created_by: t.createdBy, created_at: t.createdAt }))
      );
      await db.bulkInsert(
        "expenses",
        newExpenses.map((e) => ({ id: e.id, description: e.description, category: e.category, amount: e.amount, date: e.date, created_by: e.createdBy, created_at: e.createdAt }))
      );
      await db.bulkInsert(
        "treasury",
        newTreasury.map((t) => ({ id: t.id, type: t.type, amount: t.amount, date: t.date, note: t.note || "", created_by: t.createdBy, created_at: t.createdAt, source_transaction_id: t.sourceTransactionId || null }))
      );

      await loadAll();
    } catch (err) {
      console.error(err);
      alert("تعذّر استيراد النسخة الاحتياطية. تأكد أن النص صحيح وكامل.");
    }
    setBusy(false);
  };

  /* ---------------------------------- users (admin) ---------------------------------- */

  const toggleUserRole = async (id) => {
    const target = users.find((u) => u.id === id);
    if (!target) return;
    const adminCount = users.filter((u) => u.role === "admin").length;
    if (target.role === "admin" && adminCount <= 1) return;
    const nextRole = target.role === "admin" ? "employee" : "admin";
    const updated = await db.updateUserRole(id, nextRole);
    setUsers(users.map((u) => (u.id === id ? updated : u)));
    if (currentUser?.id === id) setCurrentUser(updated);
  };

  const deleteUserAccount = async (id) => {
    if (id === currentUser.id) return;
    const target = users.find((u) => u.id === id);
    const adminCount = users.filter((u) => u.role === "admin").length;
    if (target?.role === "admin" && adminCount <= 1) return;
    if (!confirm(`هل تريد حذف حساب "${target?.name}"؟`)) return;
    await db.deleteUser(id);
    setUsers(users.filter((u) => u.id !== id));
  };

  /* ---------------------------------- suppliers ---------------------------------- */

  const addSupplier = async (sup) => {
    const created = await db.createSupplier({ ...sup, createdBy: currentUser.username, createdAt: Date.now() });
    setSuppliers([...suppliers, created]);
  };
  const editSupplier = async (updated) => {
    const saved = await db.updateSupplier(updated);
    setSuppliers(suppliers.map((s) => (s.id === saved.id ? saved : s)));
  };
  const deleteSupplierAccount = async (id) => {
    if (currentUser.role !== "admin") return;
    if (!confirm("هل تريد حذف هذا المورد؟ سيتم حذف جميع دفعاته المرتبطة به.")) return;
    await db.deleteSupplier(id); // transactions cascade in Postgres (see schema.sql)
    setSuppliers(suppliers.filter((s) => s.id !== id));
    setTransactions(transactions.filter((t) => t.supplierId !== id));
  };

  /* ---------------------------------- transactions + treasury auto-sync ---------------------------------- */

  const addTransaction = async (tx) => {
    const created = await db.createTransaction({ ...tx, createdBy: currentUser.username, createdAt: Date.now() });
    setTransactions([...transactions, created]);

    // "دفع" -> automatically credit it to cash liquidity, linked so edits/deletes stay in sync.
    if (created.type === "to") {
      const supplierName = suppliers.find((s) => s.id === created.supplierId)?.name || "";
      const entry = await db.createTreasuryEntry({
        id: genId(),
        type: "cash",
        amount: Number(created.amount),
        date: created.date,
        note: supplierName ? `دفعة من ${supplierName}` : "دفعة من مورد",
        createdAt: Date.now(),
        createdBy: currentUser.username,
        sourceTransactionId: created.id,
      });
      setTreasury((prev) => [...prev, entry]);
    }
  };

  const editTransaction = async (updated) => {
    const saved = await db.updateTransaction(updated);
    setTransactions(transactions.map((t) => (t.id === saved.id ? saved : t)));

    const existingLinked = treasury.find((tr) => tr.sourceTransactionId === saved.id);

    if (saved.type === "to") {
      const supplierName = suppliers.find((s) => s.id === saved.supplierId)?.name || "";
      const noteText = supplierName ? `دفعة من ${supplierName}` : "دفعة من مورد";
      if (existingLinked) {
        const updatedEntry = await db.updateTreasuryEntry(existingLinked.id, { amount: saved.amount, date: saved.date, note: noteText });
        setTreasury(treasury.map((tr) => (tr.id === updatedEntry.id ? updatedEntry : tr)));
      } else {
        const entry = await db.createTreasuryEntry({
          id: genId(),
          type: "cash",
          amount: Number(saved.amount),
          date: saved.date,
          note: noteText,
          createdAt: Date.now(),
          createdBy: currentUser.username,
          sourceTransactionId: saved.id,
        });
        setTreasury([...treasury, entry]);
      }
    } else if (existingLinked) {
      await db.deleteTreasuryEntry(existingLinked.id);
      setTreasury(treasury.filter((tr) => tr.id !== existingLinked.id));
    }
  };

  const deleteTransactionEntry = async (id) => {
    if (currentUser.role !== "admin") return;
    await db.deleteTransaction(id);
    setTransactions(transactions.filter((t) => t.id !== id));
    const hadLinked = treasury.some((tr) => tr.sourceTransactionId === id);
    if (hadLinked) {
      await db.deleteTreasuryBySourceTransaction(id);
      setTreasury(treasury.filter((tr) => tr.sourceTransactionId !== id));
    }
  };

  /* ---------------------------------- expenses ---------------------------------- */

  const addExpense = async (exp) => {
    const created = await db.createExpense({ ...exp, createdBy: currentUser.username, createdAt: Date.now() });
    setExpenses([...expenses, created]);
  };
  const deleteExpenseEntry = async (id) => {
    if (currentUser.role !== "admin") return;
    await db.deleteExpense(id);
    setExpenses(expenses.filter((e) => e.id !== id));
  };

  /* ---------------------------------- treasury (manual entries) ---------------------------------- */

  const addTreasuryEntry = async (entry) => {
    const created = await db.createTreasuryEntry({ ...entry, createdBy: currentUser.username, createdAt: Date.now() });
    setTreasury([...treasury, created]);
  };
  const deleteTreasuryEntryManual = async (id) => {
    if (currentUser.role !== "admin") return;
    await db.deleteTreasuryEntry(id);
    setTreasury(treasury.filter((t) => t.id !== id));
  };

  /* ---------------------------------- visibility scoping ---------------------------------- */

  const isAdmin = currentUser?.role === "admin";

  const visibleSuppliers = useMemo(
    () => (isAdmin ? suppliers : suppliers.filter((s) => s.createdBy === currentUser?.username)),
    [suppliers, isAdmin, currentUser]
  );
  const visibleTransactions = useMemo(
    () => (isAdmin ? transactions : transactions.filter((t) => t.createdBy === currentUser?.username)),
    [transactions, isAdmin, currentUser]
  );
  const visibleExpenses = useMemo(
    () => (isAdmin ? expenses : expenses.filter((e) => e.createdBy === currentUser?.username)),
    [expenses, isAdmin, currentUser]
  );
  const visibleTreasury = useMemo(
    () => (isAdmin ? treasury : treasury.filter((t) => t.createdBy === currentUser?.username)),
    [treasury, isAdmin, currentUser]
  );
  const visibleSelectedSupplier = useMemo(
    () => visibleSuppliers.find((s) => s.id === selectedSupplierId) || null,
    [visibleSuppliers, selectedSupplierId]
  );

  /* ---------------------------------- render ---------------------------------- */

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: COLORS.paper }}>
        <Loader2 size={28} className="animate-spin" color={COLORS.ledger} />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: COLORS.paper }} dir="rtl">
        <div className="w-full max-w-sm rounded-2xl p-6 text-center font-body" style={{ background: COLORS.card, border: `1px solid ${COLORS.line}` }}>
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-4" style={{ background: COLORS.brickSoft }}>
            <AlertCircle size={24} color={COLORS.brick} />
          </div>
          <h2 className="font-display text-lg font-bold mb-2" style={{ color: COLORS.ledger }}>تعذّر الاتصال بقاعدة البيانات</h2>
          <p className="text-sm mb-5" style={{ color: COLORS.inkSoft }}>{loadError}</p>
          <Button className="w-full" onClick={loadAll}>إعادة المحاولة</Button>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="font-body">
        {authScreen === "login" ? (
          <LoginScreen
            onLogin={handleLogin}
            goRegister={() => { setAuthScreen("register"); setAuthError(""); }}
            loading={busy}
            error={loginError}
            onResetAll={handleResetAll}
          />
        ) : (
          <RegisterScreen
            onRegister={handleRegister}
            goLogin={() => { setAuthScreen("login"); setLoginError(""); }}
            users={users}
            loading={busy}
            serverError={authError}
          />
        )}
      </div>
    );
  }

  const activeTab = visibleSelectedSupplier ? "suppliers" : tab;

  return (
    <div className="flex flex-col lg:flex-row min-h-screen font-body" style={{ background: COLORS.paper }} dir="rtl">
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
        setTab={(t) => { setTab(t); setSelectedSupplierId(null); setMobileNavOpen(false); }}
        currentUser={currentUser}
        onLogout={handleLogout}
        mobileOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        isDesktop={isDesktop}
      />
      <div style={{ flex: 1, minWidth: 0, width: "100%", maxWidth: 1152, padding: isDesktop ? 32 : 16 }}>
        {visibleSelectedSupplier ? (
          <SupplierDetail
            supplier={visibleSelectedSupplier}
            transactions={visibleTransactions}
            onBack={() => setSelectedSupplierId(null)}
            onAddTx={addTransaction}
            onEditTx={editTransaction}
            onDeleteTx={deleteTransactionEntry}
            onEdit={editSupplier}
            isAdmin={isAdmin}
          />
        ) : tab === "dashboard" ? (
          <Dashboard suppliers={visibleSuppliers} transactions={visibleTransactions} expenses={visibleExpenses} isAdmin={isAdmin} />
        ) : tab === "suppliers" ? (
          <SuppliersView
            suppliers={visibleSuppliers}
            transactions={visibleTransactions}
            onAdd={addSupplier}
            onEdit={editSupplier}
            onDelete={deleteSupplierAccount}
            onOpen={setSelectedSupplierId}
            isAdmin={isAdmin}
          />
        ) : tab === "expenses" ? (
          <ExpensesView expenses={visibleExpenses} onAdd={addExpense} onDelete={deleteExpenseEntry} isAdmin={isAdmin} />
        ) : tab === "treasury" ? (
          <TreasuryView treasury={visibleTreasury} expenses={visibleExpenses} onAdd={addTreasuryEntry} onDelete={deleteTreasuryEntryManual} isAdmin={isAdmin} />
        ) : tab === "users" && isAdmin ? (
          <UsersView
            users={users}
            currentUser={currentUser}
            onToggleRole={toggleUserRole}
            onDelete={deleteUserAccount}
            suppliers={suppliers}
            transactions={transactions}
            expenses={expenses}
            treasury={treasury}
            onImportBackup={handleImportBackup}
          />
        ) : (
          <ReportsView suppliers={visibleSuppliers} transactions={visibleTransactions} expenses={visibleExpenses} isAdmin={isAdmin} />
        )}
      </div>
    </div>
  );
}
