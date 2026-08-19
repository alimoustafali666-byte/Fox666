import { supabase } from "./supabaseClient";

/**
 * Data access layer. Every function here talks to Supabase (Postgres)
 * instead of Claude's window.storage. Row shapes are mapped between
 * Postgres snake_case columns and the camelCase fields the UI expects,
 * so the rest of the app (App.jsx and all the view components) barely
 * had to change at all.
 *
 * See supabase/schema.sql for the table definitions these calls assume.
 */

function must(res, label) {
  if (res.error) {
    console.error(`[db] ${label} failed:`, res.error);
    throw res.error;
  }
  return res.data;
}

/* ---------------------------------- users ---------------------------------- */

const mapUser = (r) => ({
  id: r.id,
  name: r.name,
  username: r.username,
  role: r.role,
  passwordHash: r.password_hash,
  passwordSalt: r.password_salt,
  createdAt: r.created_at,
});

export async function listUsers() {
  const res = await supabase.from("users").select("*").order("created_at", { ascending: true });
  return must(res, "listUsers").map(mapUser);
}

export async function createUser(user) {
  const res = await supabase
    .from("users")
    .insert({
      id: user.id,
      name: user.name,
      username: user.username,
      role: user.role,
      password_hash: user.passwordHash,
      password_salt: user.passwordSalt,
      created_at: user.createdAt,
    })
    .select()
    .single();
  return mapUser(must(res, "createUser"));
}

export async function updateUserRole(id, role) {
  const res = await supabase.from("users").update({ role }).eq("id", id).select().single();
  return mapUser(must(res, "updateUserRole"));
}

export async function deleteUser(id) {
  const res = await supabase.from("users").delete().eq("id", id);
  must(res, "deleteUser");
}

/* ---------------------------------- suppliers ---------------------------------- */

const mapSupplier = (r) => ({
  id: r.id,
  name: r.name,
  phone: r.phone,
  notes: r.notes,
  createdBy: r.created_by,
  createdAt: r.created_at,
});

export async function listSuppliers() {
  const res = await supabase.from("suppliers").select("*").order("created_at", { ascending: true });
  return must(res, "listSuppliers").map(mapSupplier);
}

export async function createSupplier(sup) {
  const res = await supabase
    .from("suppliers")
    .insert({
      id: sup.id,
      name: sup.name,
      phone: sup.phone || "",
      notes: sup.notes || "",
      created_by: sup.createdBy,
      created_at: sup.createdAt,
    })
    .select()
    .single();
  return mapSupplier(must(res, "createSupplier"));
}

export async function updateSupplier(supplier) {
  const res = await supabase
    .from("suppliers")
    .update({ name: supplier.name, phone: supplier.phone || "", notes: supplier.notes || "" })
    .eq("id", supplier.id)
    .select()
    .single();
  return mapSupplier(must(res, "updateSupplier"));
}

export async function deleteSupplier(id) {
  // transactions for this supplier cascade-delete via the FK in schema.sql
  const res = await supabase.from("suppliers").delete().eq("id", id);
  must(res, "deleteSupplier");
}

/* ---------------------------------- transactions ---------------------------------- */

const mapTransaction = (r) => ({
  id: r.id,
  supplierId: r.supplier_id,
  type: r.type,
  amount: Number(r.amount),
  date: r.date,
  note: r.note,
  createdBy: r.created_by,
  createdAt: r.created_at,
});

export async function listTransactions() {
  const res = await supabase.from("transactions").select("*").order("created_at", { ascending: true });
  return must(res, "listTransactions").map(mapTransaction);
}

export async function createTransaction(tx) {
  const res = await supabase
    .from("transactions")
    .insert({
      id: tx.id,
      supplier_id: tx.supplierId,
      type: tx.type,
      amount: tx.amount,
      date: tx.date,
      note: tx.note || "",
      created_by: tx.createdBy,
      created_at: tx.createdAt,
    })
    .select()
    .single();
  return mapTransaction(must(res, "createTransaction"));
}

export async function updateTransaction(tx) {
  const res = await supabase
    .from("transactions")
    .update({ type: tx.type, amount: tx.amount, date: tx.date, note: tx.note || "" })
    .eq("id", tx.id)
    .select()
    .single();
  return mapTransaction(must(res, "updateTransaction"));
}

export async function deleteTransaction(id) {
  const res = await supabase.from("transactions").delete().eq("id", id);
  must(res, "deleteTransaction");
}

/* ---------------------------------- expenses ---------------------------------- */

const mapExpense = (r) => ({
  id: r.id,
  description: r.description,
  category: r.category,
  amount: Number(r.amount),
  date: r.date,
  createdBy: r.created_by,
  createdAt: r.created_at,
});

export async function listExpenses() {
  const res = await supabase.from("expenses").select("*").order("created_at", { ascending: true });
  return must(res, "listExpenses").map(mapExpense);
}

export async function createExpense(exp) {
  const res = await supabase
    .from("expenses")
    .insert({
      id: exp.id,
      description: exp.description,
      category: exp.category,
      amount: exp.amount,
      date: exp.date,
      created_by: exp.createdBy,
      created_at: exp.createdAt,
    })
    .select()
    .single();
  return mapExpense(must(res, "createExpense"));
}

export async function deleteExpense(id) {
  const res = await supabase.from("expenses").delete().eq("id", id);
  must(res, "deleteExpense");
}

/* ---------------------------------- treasury ---------------------------------- */

const mapTreasury = (r) => ({
  id: r.id,
  type: r.type,
  amount: Number(r.amount),
  date: r.date,
  note: r.note,
  createdBy: r.created_by,
  createdAt: r.created_at,
  sourceTransactionId: r.source_transaction_id,
});

export async function listTreasury() {
  const res = await supabase.from("treasury").select("*").order("created_at", { ascending: true });
  return must(res, "listTreasury").map(mapTreasury);
}

export async function createTreasuryEntry(entry) {
  const res = await supabase
    .from("treasury")
    .insert({
      id: entry.id,
      type: entry.type,
      amount: entry.amount,
      date: entry.date,
      note: entry.note || "",
      created_by: entry.createdBy,
      created_at: entry.createdAt,
      source_transaction_id: entry.sourceTransactionId || null,
    })
    .select()
    .single();
  return mapTreasury(must(res, "createTreasuryEntry"));
}

export async function updateTreasuryEntry(id, patch) {
  const res = await supabase
    .from("treasury")
    .update({ amount: patch.amount, date: patch.date, note: patch.note || "" })
    .eq("id", id)
    .select()
    .single();
  return mapTreasury(must(res, "updateTreasuryEntry"));
}

export async function deleteTreasuryEntry(id) {
  const res = await supabase.from("treasury").delete().eq("id", id);
  must(res, "deleteTreasuryEntry");
}

export async function deleteTreasuryBySourceTransaction(sourceTransactionId) {
  const res = await supabase.from("treasury").delete().eq("source_transaction_id", sourceTransactionId);
  must(res, "deleteTreasuryBySourceTransaction");
}

/* ---------------------------------- bulk (reset / backup import) ---------------------------------- */

export async function wipeAllData() {
  // order matters: transactions/treasury reference suppliers, so clear them first
  await supabase.from("treasury").delete().neq("id", "");
  await supabase.from("transactions").delete().neq("id", "");
  await supabase.from("expenses").delete().neq("id", "");
  await supabase.from("suppliers").delete().neq("id", "");
  await supabase.from("users").delete().neq("id", "");
}

export async function bulkInsert(table, rows) {
  if (!rows || rows.length === 0) return;
  const res = await supabase.from(table).insert(rows);
  must(res, `bulkInsert(${table})`);
}
