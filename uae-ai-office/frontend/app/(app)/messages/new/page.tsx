"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCollaboration } from "@/components/collaboration/CollaborationContext";
import { projectsApi, tenancyApi } from "@/lib/api-client";
import { errorMessage, useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import clsx from "@/components/ui/clsx";
import {
  Disclosure,
  SkeletonRows,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspaceScroller,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
} from "@/components/ui/Workspace";
import {
  MessagesIcon,
  ShieldIcon,
  TargetIcon,
  TeamIcon,
} from "@/components/layout/icons";
import type { CompanyMemberPublic, ProjectPublic } from "@/lib/types";
import styles from "../New.module.css";

type ConversationKind = "direct" | "group" | "project_channel";

export default function NewConversationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const { user, role } = useAuth();
  const { createDirect, createGroup, createProjectChannel } = useCollaboration();
  const canInvite = role === "owner" || role === "admin";

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
  const noColleagues = !loading && memberOptions.length === 0;

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

  const panelTitle =
    kind === "direct"
      ? t("messages.newConversation.directTitle")
      : kind === "group"
        ? t("messages.newConversation.groupTitle")
        : t("messages.newConversation.channelTitle");

  return (
    <WorkspaceScroller module="messages">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="cyan"
        badge={t("workspace.newConversation.badge")}
        icon={<MessagesIcon />}
        title={panelTitle}
        description={t("workspace.newConversation.description")}
        actions={
          <Link href="/messages" className={buttonClassName("secondary", "md")}>
            {t("nav.messages")}
          </Link>
        }
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="cyan" icon={<MessagesIcon />} title={panelTitle}>
            <div className={styles.tabs}>
              <button
                type="button"
                className={clsx(styles.tab, kind === "direct" && styles.tabActive)}
                onClick={() => setKind("direct")}
              >
                {t("messages.newDirect")}
              </button>
              <button
                type="button"
                className={clsx(styles.tab, kind === "group" && styles.tabActive)}
                onClick={() => setKind("group")}
              >
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

            {loading ? (
              <SkeletonRows count={5} />
            ) : noColleagues && kind === "direct" ? (
              <ZeroState
                accent="cyan"
                icon={<TeamIcon />}
                title={t("workspace.newConversation.noMembersTitle")}
                text={t("workspace.newConversation.noMembersText")}
                actions={
                  canInvite ? (
                    <Link href="/settings/team" className={buttonClassName("primary", "sm")}>
                      {t("workspace.newConversation.inviteCta")}
                    </Link>
                  ) : undefined
                }
              />
            ) : (
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                {kind === "direct" ? (
                  <FieldWrapper label={t("messages.newConversation.memberLabel")} htmlFor="member">
                    <Select
                      id="member"
                      value={selectedMemberId}
                      onChange={(e) => setSelectedMemberId(e.target.value)}
                      required
                    >
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
                        <Select
                          id="project"
                          value={selectedProjectId}
                          onChange={(e) => setSelectedProjectId(e.target.value)}
                          required
                        >
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
                        rows={3}
                        maxLength={2000}
                      />
                    </FieldWrapper>

                    <FieldWrapper
                      label={t("messages.newConversation.membersLabel")}
                      hint={t("messages.newConversation.selectMembersHint")}
                    >
                      {memberOptions.length === 0 ? (
                        <ZeroState
                          accent="cyan"
                          icon={<TeamIcon />}
                          title={t("workspace.newConversation.noMembersTitle")}
                          text={t("workspace.newConversation.noMembersText")}
                          actions={
                            canInvite ? (
                              <Link href="/settings/team" className={buttonClassName("primary", "sm")}>
                                {t("workspace.newConversation.inviteCta")}
                              </Link>
                            ) : undefined
                          }
                        />
                      ) : (
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
                      )}
                    </FieldWrapper>
                  </>
                )}

                <div style={{ display: "flex", gap: "var(--space-3)" }}>
                  <Button type="submit" loading={submitting}>
                    {submitting ? t("messages.newConversation.creating") : t("messages.newConversation.createButton")}
                  </Button>
                  <Button type="button" variant="secondary" onClick={() => router.push("/messages")}>
                    {t("messages.newConversation.cancelButton")}
                  </Button>
                </div>
              </form>
            )}
          </WorkspacePanel>

        </WorkspaceColumn>

        <WorkspaceColumn>
          <Disclosure accent="green" icon={<TargetIcon />} label={t("workspace.newConversation.guidanceTitle")}>
            <StepList
              accent="green"
              steps={[
                { title: t("workspace.newConversation.guidance.oneTitle"), description: t("workspace.newConversation.guidance.oneDescription") },
                { title: t("workspace.newConversation.guidance.twoTitle"), description: t("workspace.newConversation.guidance.twoDescription") },
                { title: t("workspace.newConversation.guidance.threeTitle"), description: t("workspace.newConversation.guidance.threeDescription") },
              ]}
            />
          </Disclosure>

          {canInvite ? (
            <WorkspacePanel accent="violet" icon={<TeamIcon />} title={t("workspace.newConversation.inviteCta")} tight>
              <div style={{ padding: "var(--space-3)" }}>
                <Link href="/settings/team" className={buttonClassName("secondary", "sm", true)}>
                  {t("workspace.newConversation.inviteCta")}
                </Link>
              </div>
            </WorkspacePanel>
          ) : null}

          <WorkspaceNote accent="cyan" icon={<ShieldIcon />}>
            {t("workspace.newConversation.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspaceScroller>
  );
}
