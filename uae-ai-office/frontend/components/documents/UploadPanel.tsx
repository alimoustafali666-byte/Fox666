"use client";

import { useEffect, useState, type FormEvent } from "react";
import { documentsApi, projectsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input, Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { DOCUMENT_TYPES, type DocumentPublic, type DocumentType, type ProjectPublic } from "@/lib/types";
import { DOCUMENT_TYPE_KEYS } from "./lifecycle";
import styles from "./UploadPanel.module.css";

export function UploadPanel({
  onUploaded,
  onCancel,
}: {
  onUploaded: (doc: DocumentPublic) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [projects, setProjects] = useState<ProjectPublic[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("other");
  const [projectId, setProjectId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    projectsApi
      .list({ limit: 100 })
      .then((page) => setProjects(page.items))
      .catch(() => setProjects([]));
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError(t("documents.upload.chooseFileError"));
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const doc = await documentsApi.upload({
        file,
        document_type: documentType,
        project_id: projectId || undefined,
      });
      onUploaded(doc);
    } catch (err) {
      setError(errorMessage(err, t("documents.upload.genericError")));
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
            <div className={styles.fileRow}>
              <FieldWrapper label={t("documents.upload.fileLabel")} htmlFor="file" hint={t("documents.upload.fileHint")}>
                <Input
                  id="file"
                  type="file"
                  accept=".pdf,.doc,.docx,.xls,.xlsx"
                  required
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </FieldWrapper>
            </div>

            <FieldWrapper label={t("documents.upload.documentType")} htmlFor="document_type">
              <Select
                id="document_type"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value as DocumentType)}
              >
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(DOCUMENT_TYPE_KEYS[type])}
                  </option>
                ))}
              </Select>
            </FieldWrapper>

            <FieldWrapper label={t("documents.upload.project")} htmlFor="project_id" optional>
              <Select id="project_id" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">{t("common.noProject")}</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            </FieldWrapper>
          </div>

          <div className={styles.actions}>
            <Button type="button" variant="secondary" onClick={onCancel} disabled={submitting}>
              {t("documents.upload.cancel")}
            </Button>
            <Button type="submit" loading={submitting}>
              {submitting ? t("documents.upload.submitting") : t("documents.upload.submit")}
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

