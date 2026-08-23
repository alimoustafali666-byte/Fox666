"use client";

import { useCallback, useEffect, useState } from "react";
import { collaborationApi, tenancyApi } from "@/lib/api-client";
import { errorMessage, useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Spinner } from "@/components/ui/Spinner";
import type { ChatConversationPublic, CompanyMemberPublic, ConversationMemberPublic, NotificationPref } from "@/lib/types";
import styles from "./MembersPanel.module.css";

interface MembersPanelProps {
  conversation: ChatConversationPublic;
  onClose: () => void;
  onRenamed: (patch: Partial<ChatConversationPublic>) => void;
  onLeft: () => void;
}

export function MembersPanel({ conversation, onClose, onRenamed, onLeft }: MembersPanelProps) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [members, setMembers] = useState<ConversationMemberPublic[]>([]);
  const [companyMembers, setCompanyMembers] = useState<CompanyMemberPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addSelection, setAddSelection] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState(conversation.name || "");
  const [description, setDescription] = useState(conversation.description || "");

  const isDirect = conversation.type === "direct";
  const self = members.find((m) => m.user_id === user?.id);
  const isAdmin = self ? self.role === "owner" || self.role === "admin" : false;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [memberList, companyList] = await Promise.all([
        collaborationApi.listMembers(conversation.id),
        tenancyApi.listMembers(),
      ]);
      setMembers(memberList);
      setCompanyMembers(companyList);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [conversation.id]);

  useEffect(() => {
    load();
  }, [load]);

  const addableMembers = companyMembers.filter((cm) => !members.some((m) => m.user_id === cm.user_id));

  async function handleAddMember() {
    if (!addSelection) return;
    setBusy(true);
    setError(null);
    try {
      const member = await collaborationApi.addMember(conversation.id, addSelection);
      setMembers((prev) => [...prev, member]);
      setAddSelection("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRemoveMember(userId: string, name_: string) {
    if (!window.confirm(t("messages.members.confirmRemove", { name: name_ }))) return;
    setBusy(true);
    setError(null);
    try {
      await collaborationApi.removeMember(conversation.id, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleLeave() {
    if (!window.confirm(t("messages.members.confirmLeave"))) return;
    setBusy(true);
    setError(null);
    try {
      await collaborationApi.leave(conversation.id);
      onLeft();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function handleRename() {
    setBusy(true);
    setError(null);
    try {
      await collaborationApi.rename(conversation.id, { name: name.trim() || null, description: description.trim() || null });
      onRenamed({ name: name.trim() || null, description: description.trim() || null });
    } catch (err) {
      setError(errorMessage(err, t("messages.members.genericError")));
    } finally {
      setBusy(false);
    }
  }

  async function handleNotificationPrefChange(pref: NotificationPref) {
    setBusy(true);
    try {
      await collaborationApi.updateNotificationPref(conversation.id, pref);
      setMembers((prev) => prev.map((m) => (m.user_id === user?.id ? { ...m, notification_pref: pref } : m)));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.title}>{t("messages.members.title")}</div>
        <button type="button" className={styles.closeButton} onClick={onClose}>
          ✕
        </button>
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      {loading ? (
        <Spinner size="sm" />
      ) : (
        <>
          {!isDirect && isAdmin ? (
            <div className={styles.section}>
              <FieldWrapper label={t("messages.members.nameLabel")} htmlFor="conv-name">
                <Input id="conv-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
              </FieldWrapper>
              <FieldWrapper label={t("messages.members.descriptionLabel")} htmlFor="conv-desc" optional>
                <Textarea id="conv-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={2000} />
              </FieldWrapper>
              <Button size="sm" onClick={handleRename} loading={busy}>
                {t("messages.members.saveButton")}
              </Button>
            </div>
          ) : null}

          <div className={styles.section}>
            <FieldWrapper label={t("messages.members.notificationPrefLabel")} htmlFor="notif-pref">
              <Select
                id="notif-pref"
                value={self?.notification_pref ?? "all"}
                onChange={(e) => handleNotificationPrefChange(e.target.value as NotificationPref)}
              >
                <option value="all">{t("messages.members.notificationPrefAll")}</option>
                <option value="mentions">{t("messages.members.notificationPrefMentions")}</option>
                <option value="muted">{t("messages.members.notificationPrefMuted")}</option>
              </Select>
            </FieldWrapper>
          </div>

          <div className={styles.section}>
            <div className={styles.memberList}>
              {members.map((m) => (
                <div key={m.user_id} className={styles.memberRow}>
                  <div>
                    <div className={styles.memberName}>{m.full_name || m.user_id}</div>
                    <div className={styles.memberRole}>
                      {m.role === "owner" ? t("messages.members.roleOwner") : m.role === "admin" ? t("messages.members.roleAdmin") : t("messages.members.roleMember")}
                    </div>
                  </div>
                  {isAdmin && m.user_id !== user?.id ? (
                    <button type="button" className={styles.removeButton} onClick={() => handleRemoveMember(m.user_id, m.full_name || "")} disabled={busy}>
                      {t("messages.members.removeAction")}
                    </button>
                  ) : null}
                </div>
              ))}
            </div>

            {!isDirect && isAdmin ? (
              <div className={styles.addRow}>
                <Select value={addSelection} onChange={(e) => setAddSelection(e.target.value)}>
                  <option value="">{t("messages.members.addPlaceholder")}</option>
                  {addableMembers.map((cm) => (
                    <option key={cm.user_id} value={cm.user_id}>
                      {cm.full_name || cm.email}
                    </option>
                  ))}
                </Select>
                <Button size="sm" onClick={handleAddMember} disabled={!addSelection} loading={busy}>
                  {t("messages.members.addButton")}
                </Button>
              </div>
            ) : null}
          </div>

          {!isDirect ? (
            <div className={styles.section}>
              <Button size="sm" variant="danger" onClick={handleLeave} loading={busy}>
                {t("messages.members.leaveButton")}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </aside>
  );
}

