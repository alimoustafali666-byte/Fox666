"use client";

import { useState, type FormEvent } from "react";
import { projectsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PROJECT_STATUSES, type ProjectPublic, type ProjectStatus } from "@/lib/types";
import { PROJECT_STATUS_KEYS } from "./statusLabels";
import styles from "./ProjectFormPanel.module.css";

export function ProjectFormPanel({
  project,
  onSaved,
  onCancel,
}: {
  project?: ProjectPublic;
  onSaved: (project: ProjectPublic) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const isEdit = Boolean(project);
  const [name, setName] = useState(project?.name ?? "");
  const [projectCode, setProjectCode] = useState(project?.project_code ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [status, setStatus] = useState<ProjectStatus>(project?.status ?? "planning");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const saved = isEdit
        ? await projectsApi.update(project!.id, {
            name,
            project_code: projectCode || null,
            description: description || null,
            status,
          })
        : await projectsApi.create({
            name,
            project_code: projectCode || undefined,
            description: description || undefined,
            status,
          });
      onSaved(saved);
    } catch (err) {
      setError(errorMessage(err, t("projects.form.genericError")));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardBody>
        {error ? (
          <div style={{ marginBottom: "var(--space-4)" }}>
            <ErrorBanner message={error} />
          </div>
        ) : null}
        <form onSubmit={handleSubmit}>
          <div className={styles.grid}>
            <FieldWrapper label={t("projects.form.nameLabel")} htmlFor="name">
              <Input
                id="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("projects.form.namePlaceholder")}
              />
            </FieldWrapper>
            <FieldWrapper label={t("projects.form.codeLabel")} htmlFor="project_code" optional>
              <Input
                id="project_code"
                value={projectCode}
                onChange={(e) => setProjectCode(e.target.value)}
                placeholder={t("projects.form.codePlaceholder")}
              />
            </FieldWrapper>
            <FieldWrapper label={t("projects.form.statusLabel")} htmlFor="status">
              <Select id="status" value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
                {PROJECT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(PROJECT_STATUS_KEYS[s])}
                  </option>
                ))}
              </Select>
            </FieldWrapper>
            <div className={styles.fullRow}>
              <FieldWrapper label={t("projects.form.descriptionLabel")} htmlFor="description" optional>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("projects.form.descriptionPlaceholder")}
                  rows={3}
                />
              </FieldWrapper>
            </div>
          </div>
          <div className={styles.actions}>
            <Button type="button" variant="secondary" onClick={onCancel} disabled={submitting}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" loading={submitting}>
              {submitting ? t("projects.form.saving") : isEdit ? t("projects.form.saveButton") : t("projects.form.createButton")}
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

