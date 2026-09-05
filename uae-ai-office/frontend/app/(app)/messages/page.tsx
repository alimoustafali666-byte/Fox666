"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, errorMessage } from "@/lib/auth-context";
import { collaborationApi, tenancyApi } from "@/lib/api-client";
import { useCollaboration } from "@/components/collaboration/CollaborationContext";
import { useTranslation, formatDate, type TranslationKey } from "@/lib/i18n";
import { buttonClassName } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  ChipRow,
  ChipLink,
  Disclosure,
  InfoList,
  InfoRow,
  PointList,
  SkeletonRows,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePanel,
  WorkspaceScroller,
  WorkspaceSplit,
  ZeroState,
} from "@/components/ui/Workspace";
import {
  BellIcon,
  BrainIcon,
  MessagesIcon,
  ProjectsIcon,
  PulseIcon,
  ShieldIcon,
  SparkIcon,
  TeamIcon,
  UploadIcon,
} from "@/components/layout/icons";
import type { ChatConversationPublic, CompanyMemberPublic, ConversationType } from "@/lib/types";
import { ROLE_LABEL_KEYS } from "@/components/layout/roles";

const NOTIFICATION_SCAN_LIMIT = 30;

const TYPE_KEY: Record<ConversationType, TranslationKey> = {
  direct: "messages.typeLabels.direct",
  group: "messages.typeLabels.group",
  project_channel: "messages.typeLabels.project_channel",
};

export default function MessagesLandingPage() {
  const { t, locale } = useTranslation();
  const { user, role } = useAuth();
  const router = useRouter();
  const { conversations, loading, totalUnread, directPeerNames, createDirect } = useCollaboration();

  const canInvite = role === "owner" || role === "admin";
  const [members, setMembers] = useState<CompanyMemberPublic[] | null>(null);
  const [loadingMembers, setLoadingMembers] = useState(true);
  const [unreadNotifications, setUnreadNotifications] = useState<number | null>(null);
  const [startingWith, setStartingWith] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Both panels below are fed from existing read-only endpoints and settle
  // independently, so one being role-scoped or unavailable leaves that panel
  // in a neutral state instead of blanking the workspace.
  useEffect(() => {
    let cancelled = false;
    tenancyApi
      .listMembers()
      .then((list) => {
        if (!cancelled) setMembers(list);
      })
      .catch(() => {
        if (!cancelled) setMembers(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingMembers(false);
      });

    collaborationApi
      .listNotifications({ unread_only: true, limit: NOTIFICATION_SCAN_LIMIT })
      .then((page) => {
        if (!cancelled) setUnreadNotifications(page.items.length);
      })
      .catch(() => {
        if (!cancelled) setUnreadNotifications(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const otherMembers = useMemo(
    () => (members ?? []).filter((member) => member.user_id !== user?.id),
    [members, user?.id]
  );

  const channelCount = useMemo(
    () => conversations.filter((c) => c.type === "project_channel").length,
    [conversations]
  );

  const recent = useMemo(
    () =>
      [...conversations]
        .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
        .slice(0, 10),
    [conversations]
  );

  function conversationTitle(conversation: ChatConversationPublic): string {
    if (conversation.type === "direct") {
      return directPeerNames[conversation.id] || t("messages.untitledDirect");
    }
    return conversation.name || t("messages.untitledGroup");
  }

  async function startDirect(member: CompanyMemberPublic) {
    if (startingWith) return;
    setStartingWith(member.user_id);
    setError(null);
    try {
      const conversation = await createDirect(member.user_id);
      router.push(`/messages/${conversation.id}`);
    } catch (err) {
      setError(errorMessage(err, t("messages.genericListError")));
      setStartingWith(null);
    }
  }

  return (
    <WorkspaceScroller module="messages">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="cyan"
        compact
        badge={t("workspace.messages.badge")}
        icon={<MessagesIcon />}
        title={t("workspace.messages.title")}
        description={t("workspace.messages.description")}
        actions={
          <>
            <Link href="/messages/new?type=direct" className={buttonClassName("primary", "md")}>
              {t("messages.newDirect")}
            </Link>
            <ChipRow>
              <ChipLink accent="violet" href="/messages/new?type=group" icon={<TeamIcon />}>
                {t("messages.newGroup")}
              </ChipLink>
              <ChipLink accent="blue" href="/messages/new?type=project_channel" icon={<ProjectsIcon />}>
                {t("messages.newChannel")}
              </ChipLink>
              <ChipLink accent="magenta" href="/messages/notifications" icon={<BellIcon />}>
                {unreadNotifications !== null && unreadNotifications > 0
                  ? `${t("messages.notificationsLink")} · ${unreadNotifications}`
                  : t("messages.notificationsLink")}
              </ChipLink>
            </ChipRow>
          </>
        }
        metrics={[
          {
            label: t("workspace.messages.metrics.conversationsLabel"),
            value: loading ? "—" : conversations.length,
            hint: t("workspace.messages.metrics.conversationsHint"),
            icon: <MessagesIcon />,
          },
          {
            label: t("workspace.messages.metrics.unreadLabel"),
            value: loading ? "—" : totalUnread,
            hint: t("workspace.messages.metrics.unreadHint"),
            icon: <PulseIcon />,
          },
          {
            label: t("workspace.messages.metrics.teamLabel"),
            value: members ? members.length : "—",
            hint: t("workspace.messages.metrics.teamHint"),
            icon: <TeamIcon />,
          },
          {
            label: t("workspace.messages.metrics.channelsLabel"),
            value: loading ? "—" : channelCount,
            hint: t("workspace.messages.metrics.channelsHint"),
            icon: <ProjectsIcon />,
          },
        ]}
      />

      <WorkspaceSplit wide>
        <WorkspaceColumn>
          <WorkspacePanel
            accent="violet"
            icon={<TeamIcon />}
            title={t("workspace.messages.teamTitle")}
            subtitle={t("workspace.messages.teamSubtitle")}
            tight
            action={
              <Link href="/settings/team" className={buttonClassName("ghost", "sm")}>
                {t("workspace.messages.teamAll")}
              </Link>
            }
          >
            {loadingMembers ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={4} />
              </div>
            ) : members === null ? (
              <ZeroState accent="amber" icon={<TeamIcon />} title={t("workspace.messages.teamUnavailable")} />
            ) : otherMembers.length === 0 ? (
              <ZeroState
                accent="violet"
                icon={<TeamIcon />}
                title={t("workspace.messages.teamEmptyTitle")}
                text={t("workspace.messages.teamEmptyText")}
                actions={
                  canInvite ? (
                    <Link href="/settings/team" className={buttonClassName("primary", "sm")}>
                      {t("workspace.messages.teamInvite")}
                    </Link>
                  ) : undefined
                }
              />
            ) : (
              <InfoList>
                {otherMembers.map((member) => (
                  <InfoRow
                    key={member.user_id}
                    accent="violet"
                    icon={<TeamIcon />}
                    label={member.full_name || member.email}
                    meta={t(ROLE_LABEL_KEYS[member.role])}
                    value={startingWith === member.user_id ? t("common.loading") : t("workspace.messages.messageAction")}
                    onClick={() => startDirect(member)}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>

          <Disclosure accent="cyan" icon={<SparkIcon />} label={t("workspace.messages.howLabel")}>
            <PointList
              accent="cyan"
              items={[
                {
                  icon: <UploadIcon />,
                  title: t("workspace.messages.features.attachmentsTitle"),
                  text: t("workspace.messages.features.attachmentsDescription"),
                },
                {
                  icon: <PulseIcon />,
                  title: t("workspace.messages.features.callsTitle"),
                  text: t("workspace.messages.features.callsDescription"),
                },
                {
                  icon: <BrainIcon />,
                  title: t("workspace.messages.features.aiTitle"),
                  text: t("workspace.messages.features.aiDescription"),
                },
                {
                  icon: <TeamIcon />,
                  title: t("workspace.messages.features.presenceTitle"),
                  text: t("workspace.messages.features.presenceDescription"),
                },
              ]}
            />
            <div style={{ marginTop: "var(--space-4)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--ai-hairline)" }}>
              <StepList
                accent="green"
                steps={[
                  { title: t("workspace.messages.guidance.oneTitle"), description: t("workspace.messages.guidance.oneDescription") },
                  { title: t("workspace.messages.guidance.twoTitle"), description: t("workspace.messages.guidance.twoDescription") },
                  { title: t("workspace.messages.guidance.threeTitle"), description: t("workspace.messages.guidance.threeDescription") },
                  { title: t("workspace.messages.guidance.fourTitle"), description: t("workspace.messages.guidance.fourDescription") },
                ]}
              />
            </div>
          </Disclosure>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="cyan"
            icon={<MessagesIcon />}
            title={t("workspace.messages.recentTitle")}
            subtitle={t("workspace.messages.recentSubtitle")}
            tight
          >
            {loading ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={5} />
              </div>
            ) : recent.length === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<MessagesIcon />}
                title={t("workspace.messages.recentEmptyTitle")}
                text={t("workspace.messages.recentEmptyText")}
                actions={
                  <Link href="/messages/new?type=direct" className={buttonClassName("primary", "sm")}>
                    {t("messages.newDirect")}
                  </Link>
                }
              />
            ) : (
              <InfoList>
                {recent.map((conversation) => (
                  <InfoRow
                    key={conversation.id}
                    accent="cyan"
                    icon={<MessagesIcon />}
                    href={`/messages/${conversation.id}`}
                    label={conversationTitle(conversation)}
                    meta={`${t(TYPE_KEY[conversation.type])} · ${formatDate(locale, conversation.updated_at, { month: "short", day: "numeric" })}`}
                    value={conversation.unread_count > 0 ? conversation.unread_count : undefined}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>

          <WorkspaceNote accent="green" icon={<ShieldIcon />}>
            {t("workspace.messages.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspaceScroller>
  );
}
