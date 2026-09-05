"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { collectDiagnostics } from "@/lib/support-diagnostics";
import { Button, buttonClassName } from "@/components/ui/Button";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ApiError } from "@/lib/api-client";
import {
  Disclosure,
  InfoList,
  InfoRow,
  PointList,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
} from "@/components/ui/Workspace";
import {
  BrainIcon,
  DocumentsIcon,
  HelpIcon,
  InsightIcon,
  ShieldIcon,
  TargetIcon,
  TicketIcon,
} from "@/components/layout/icons";
import { CATEGORY_LABEL_KEYS, PRIORITY_LABEL_KEYS } from "@/components/support/labels";
import {
  SUPPORT_TICKET_CATEGORIES,
  SUPPORT_TICKET_PRIORITIES,
  type SupportTicketCategory,
  type SupportTicketPriority,
} from "@/lib/types";
import styles from "../../Support.module.css";

export default function NewSupportTicketPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [category, setCategory] = useState<SupportTicketCategory>("other");
  const [subject, setSubject] = useState(searchParams.get("subject") ?? "");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<SupportTicketPriority>("normal");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const ticket = await supportApi.createTicket({
        category,
        subject,
        description,
        priority,
        diagnostics: collectDiagnostics(),
      });
      router.push(`/support/tickets/${ticket.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(t("support.newTicket.rateLimitedError"));
      } else {
        setError(errorMessage(err, t("support.newTicket.genericError")));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <WorkspacePage module="support">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="green"
        badge={t("workspace.newTicket.badge")}
        icon={<TicketIcon />}
        title={t("support.newTicket.title")}
        description={t("workspace.newTicket.description")}
        actions={
          <>
            <Link href="/support/assistant" className={buttonClassName("secondary", "md")}>
              {t("workspace.tickets.before.assistantTitle")}
            </Link>
            <Link href="/support/tickets" className={buttonClassName("ghost", "md")}>
              {t("support.tickets.title")}
            </Link>
          </>
        }
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="magenta" icon={<TicketIcon />} title={t("support.newTicket.title")}>
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              <FieldWrapper label={t("support.newTicket.categoryLabel")} htmlFor="category">
                <Select
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as SupportTicketCategory)}
                >
                  {SUPPORT_TICKET_CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {t(CATEGORY_LABEL_KEYS[c])}
                    </option>
                  ))}
                </Select>
              </FieldWrapper>

              <FieldWrapper label={t("support.newTicket.subjectLabel")} htmlFor="subject">
                <Input
                  id="subject"
                  required
                  maxLength={200}
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder={t("support.newTicket.subjectPlaceholder")}
                />
              </FieldWrapper>

              <FieldWrapper label={t("support.newTicket.descriptionLabel")} htmlFor="description">
                <Textarea
                  id="description"
                  required
                  maxLength={5000}
                  rows={7}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("support.newTicket.descriptionPlaceholder")}
                />
              </FieldWrapper>

              <FieldWrapper label={t("support.newTicket.priorityLabel")} htmlFor="priority">
                <Select
                  id="priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as SupportTicketPriority)}
                >
                  {SUPPORT_TICKET_PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {t(PRIORITY_LABEL_KEYS[p])}
                    </option>
                  ))}
                </Select>
              </FieldWrapper>

              <p className={styles.assistantNote}>{t("support.newTicket.diagnosticsNote")}</p>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
                <Button type="button" variant="secondary" onClick={() => router.push("/support")} disabled={submitting}>
                  {t("support.newTicket.cancelButton")}
                </Button>
                <Button type="submit" loading={submitting}>
                  {submitting ? t("support.newTicket.submitting") : t("support.newTicket.submitButton")}
                </Button>
              </div>
            </form>
          </WorkspacePanel>

          <Disclosure accent="cyan" icon={<InsightIcon />} label={t("workspace.newTicket.writingTitle")}>
            <PointList
              accent="cyan"
              items={[
                { icon: <TargetIcon />, title: t("workspace.newTicket.writing.stepsTitle"), text: t("workspace.newTicket.writing.stepsDescription") },
                { icon: <InsightIcon />, title: t("workspace.newTicket.writing.expectedTitle"), text: t("workspace.newTicket.writing.expectedDescription") },
                { icon: <HelpIcon />, title: t("workspace.newTicket.writing.actualTitle"), text: t("workspace.newTicket.writing.actualDescription") },
              ]}
            />
          </Disclosure>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <Disclosure accent="blue" icon={<TargetIcon />} label={t("workspace.newTicket.expectTitle")}>
            <StepList
              accent="blue"
              steps={[
                { title: t("workspace.newTicket.expect.oneTitle"), description: t("workspace.newTicket.expect.oneDescription") },
                { title: t("workspace.newTicket.expect.twoTitle"), description: t("workspace.newTicket.expect.twoDescription") },
                { title: t("workspace.newTicket.expect.threeTitle"), description: t("workspace.newTicket.expect.threeDescription") },
              ]}
            />
          </Disclosure>

          <WorkspacePanel accent="violet" icon={<BrainIcon />} title={t("workspace.tickets.beforeTitle")} tight>
            <InfoList>
              <InfoRow
                accent="violet"
                icon={<BrainIcon />}
                href="/support/assistant"
                label={t("workspace.tickets.before.assistantTitle")}
                meta={t("workspace.tickets.before.assistantDescription")}
              />
              <InfoRow
                accent="cyan"
                icon={<DocumentsIcon />}
                href="/support"
                label={t("workspace.tickets.before.articlesTitle")}
                meta={t("workspace.tickets.before.articlesDescription")}
              />
            </InfoList>
          </WorkspacePanel>

          <WorkspaceNote accent="magenta" icon={<ShieldIcon />}>
            {t("workspace.newTicket.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
