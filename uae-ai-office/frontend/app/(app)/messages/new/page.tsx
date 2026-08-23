"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCollaboration } from "@/components/collaboration/CollaborationContext";
import { projectsApi, tenancyApi } from "@/lib/api-client";
import { errorMessage, useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import clsx from "@/components/ui/clsx";
import type { CompanyMemberPublic, ProjectPublic } from "@/lib/types";
import styles from "../New.module.css";

type ConversationKind = "direct" | "group" | "project_channel";

export default function NewConversationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { createDirect, createGroup, createProjectChannel } = useCollaboration();

  const initialKind = (searchParams.get("type") as ConversationKind | null) || "direct";
  const [kind, setKind] = useState<ConversationKind>(initialKind);
  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [projects, setProjects] = useState<ProjectPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [groupDescription, setGroupDescription] = useState("");
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());
  const [selectedProjectId, setSelectedProjectId] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [memberList, projectPage] = await Promise.all([
          tenancyApi.listMembers(),
          projectsApi.list({ limit: 100 }),
        ]);
        setMembers(memberList.filter((m) => m.user_id !== user?.id));
        setProjects(projectPage.items);
      } catch {
        setError(t("messages.newConversation.genericError"));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const toggleMember = useCallback((id: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const memberOptions = useMemo(() => members, [members]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (kind === "direct") {
        if (!selectedMemberId) return;
        const conversation = await createDirect(selectedMemberId);
        router.push(`/messages/${conversation.id}`);
        return;
      }
      if (kind === "group") {
        if (!groupName.trim()) return;
        const conversation = await createGroup({
          name: groupName.trim(),
          description: groupDescription.trim() || undefined,
          member_user_ids: [...selectedMemberIds],
        });
        router.push(`/messages/${conversation.id}`);
        return;
      }
      if (!selectedProjectId || !groupName.trim()) return;
      const conversation = await createProjectChannel({
        project_id: selectedProjectId,
        name: groupName.trim(),
        description: groupDescription.trim() || undefined,
        member_user_ids: [...selectedMemberIds],
      });
      router.push(`/messages/${conversation.id}`);
    } catch (err) {
      setError(errorMessage(err, t("messages.newConversation.genericError")));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <LoadingBlock label={t("common.loading")} />;

  return (
    <div style={{ padding: "var(--space-6)", maxWidth: 560, margin: "0 auto" }}>
      <div className={styles.tabs}>
        <button type="button" className={clsx(styles.tab, kind === "direct" && styles.tabActive)} onClick={() => setKind("direct")}>
          {t("messages.newDirect")}
        </button>
        <button type="button" className={clsx(styles.tab, kind === "group" && styles.tabActive)} onClick={() => setKind("group")}>
          {t("messages.newGroup")}
        </button>
        <button
          type="button"
          className={clsx(styles.tab, kind === "project_channel" && styles.tabActive)}
          onClick={() => setKind("project_channel")}
        >
          {t("messages.newChannel")}
        </button>
      </div>

      <Card>
        <CardHeader
          title={
            kind === "direct"
              ? t("messages.newConversation.directTitle")
              : kind === "group"
                ? t("messages.newConversation.groupTitle")
                : t("messages.newConversation.channelTitle")
          }
        />
        <CardBody>
          {error ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <form onSubmit={handleSubmit}>
            {kind === "direct" ? (
              <FieldWrapper label={t("messages.newConversation.memberLabel")} htmlFor="member">
                <Select id="member" value={selectedMemberId} onChange={(e) => setSelectedMemberId(e.target.value)} required>
                  <option value="" disabled>
                    {t("messages.newConversation.memberLabel")}
                  </option>
                  {memberOptions.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.full_name || m.email}
                    </option>
                  ))}
                </Select>
              </FieldWrapper>
            ) : (
              <>
                {kind === "project_channel" ? (
                  <FieldWrapper label={t("messages.newConversation.channelProjectLabel")} htmlFor="project">
                    <Select id="project" value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} required>
                      <option value="" disabled>
                        {t("messages.newConversation.channelProjectLabel")}
                      </option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </Select>
                  </FieldWrapper>
                ) : null}

                <FieldWrapper label={t("messages.newConversation.groupNameLabel")} htmlFor="name">
                  <Input
                    id="name"
                    value={groupName}
                    onChange={(e) => setGroupName(e.target.value)}
                    placeholder={t("messages.newConversation.groupNamePlaceholder")}
                    maxLength={200}
                    required
                  />
                </FieldWrapper>

                <FieldWrapper label={t("messages.newConversation.descriptionLabel")} htmlFor="description" optional>
                  <Textarea
                    id="description"
                    value={groupDescription}
                    onChange={(e) => setGroupDescription(e.target.value)}
                    rows={2}
                    maxLength={2000}
                  />
                </FieldWrapper>

                <FieldWrapper label={t("messages.newConversation.membersLabel")} hint={t("messages.newConversation.selectMembersHint")}>
                  <div className={styles.memberChecklist}>
                    {memberOptions.map((m) => (
                      <label key={m.user_id} className={styles.memberCheckboxRow}>
                        <input
                          type="checkbox"
                          checked={selectedMemberIds.has(m.user_id)}
                          onChange={() => toggleMember(m.user_id)}
                        />
                        {m.full_name || m.email}
                      </label>
                    ))}
                  </div>
                </FieldWrapper>
              </>
            )}

            <div style={{ display: "flex", gap: "var(--space-3)", marginTop: "var(--space-5)" }}>
              <Button type="submit" loading={submitting}>
                {submitting ? t("messages.newConversation.creating") : t("messages.newConversation.createButton")}
              </Button>
              <Button type="button" variant="secondary" onClick={() => router.push("/messages")}>
                {t("messages.newConversation.cancelButton")}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}

