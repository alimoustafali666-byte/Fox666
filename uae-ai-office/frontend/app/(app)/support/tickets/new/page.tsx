"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { collectDiagnostics } from "@/lib/support-diagnostics";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ApiError } from "@/lib/api-client";
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
    <div>
      <PageHeader title={t("support.newTicket.title")} description={t("support.newTicket.description")} />

      <Card>
        <CardBody>
          {error ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <ErrorBanner message={error} />
            </div>
          ) : null}

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
                rows={5}
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
        </CardBody>
      </Card>
    </div>
  );
}

