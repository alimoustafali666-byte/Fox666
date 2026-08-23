"use client";

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useAuth } from "@/lib/auth-context";
import { ApiError, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { CompanyLogo } from "@/components/layout/CompanyLogo";
import styles from "./CompanyBrandingCard.module.css";

const MAX_LOGO_BYTES = 2 * 1024 * 1024;

export function CompanyBrandingCard() {
  const { company, role, refreshCompany } = useAuth();
  const { t } = useTranslation();
  const canManage = role === "owner" || role === "admin";
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(company?.name ?? "");
  const [timezone, setTimezone] = useState(company?.timezone ?? "");
  const [country, setCountry] = useState(company?.country ?? "");
  const [saving, setSaving] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!company) return null;

  function startEditing() {
    setName(company!.name);
    setTimezone(company!.timezone);
    setCountry(company!.country);
    setError(null);
    setEditing(true);
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await tenancyApi.updateCompany({ name, timezone, country });
      await refreshCompany();
      setEditing(false);
    } catch (err) {
      setError(errorMessage(err, t("settings.company.genericError")));
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_LOGO_BYTES) {
      setError(t("settings.company.logoTooLarge"));
      return;
    }
    setError(null);
    setLogoBusy(true);
    try {
      await tenancyApi.uploadLogo(file);
      await refreshCompany();
    } catch (err) {
      const fallback =
        err instanceof ApiError && err.code === "unsupported_logo_type"
          ? t("settings.company.logoUnsupportedType")
          : t("settings.company.logoUploadError");
      setError(errorMessage(err, fallback));
    } finally {
      setLogoBusy(false);
    }
  }

  async function handleLogoDelete() {
    setError(null);
    setLogoBusy(true);
    try {
      await tenancyApi.deleteLogo();
      await refreshCompany();
    } catch (err) {
      setError(errorMessage(err, t("settings.company.logoDeleteError")));
    } finally {
      setLogoBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title={t("settings.company.title")}
        actions={
          canManage && !editing ? (
            <Button size="sm" variant="secondary" onClick={startEditing}>
              {t("common.edit")}
            </Button>
          ) : undefined
        }
      />
      <CardBody>
        {error ? (
          <div style={{ marginBottom: "var(--space-4)" }}>
            <ErrorBanner message={error} />
          </div>
        ) : null}

        <div className={styles.logoRow}>
          <CompanyLogo hasLogo={company.has_logo} size={64} className={styles.logoImage} />
          {!company.has_logo ? <div className={styles.logoPlaceholder}>{t("settings.company.noLogo")}</div> : null}
          {canManage ? (
            <div className={styles.logoActions}>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg"
                className={styles.hiddenInput}
                onChange={handleLogoChange}
              />
              <Button size="sm" variant="secondary" onClick={() => fileInputRef.current?.click()} loading={logoBusy}>
                {company.has_logo ? t("settings.company.replaceLogo") : t("settings.company.uploadLogo")}
              </Button>
              {company.has_logo ? (
                <Button size="sm" variant="danger" onClick={handleLogoDelete} disabled={logoBusy}>
                  {t("settings.company.removeLogo")}
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className={styles.logoHint}>{t("settings.company.logoHint")}</div>

        {editing ? (
          <form onSubmit={handleSave} className={styles.form}>
            <FieldWrapper label={t("settings.company.name")} htmlFor="company-name">
              <Input id="company-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
            </FieldWrapper>
            <div className={styles.formRow}>
              <FieldWrapper label={t("settings.company.timezone")} htmlFor="company-timezone">
                <Input id="company-timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)} required />
              </FieldWrapper>
              <FieldWrapper label={t("settings.company.country")} htmlFor="company-country">
                <Input
                  id="company-country"
                  value={country}
                  onChange={(e) => setCountry(e.target.value.toUpperCase())}
                  required
                  maxLength={2}
                />
              </FieldWrapper>
            </div>
            <div className={styles.formActions}>
              <Button type="submit" size="sm" loading={saving}>
                {t("settings.company.saveButton")}
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={() => setEditing(false)} disabled={saving}>
                {t("common.cancel")}
              </Button>
            </div>
          </form>
        ) : (
          <div className={styles.companyGrid}>
            <div>
              <div className={styles.metaLabel}>{t("settings.company.name")}</div>
              <div className={styles.metaValue}>{company.name}</div>
            </div>
            <div>
              <div className={styles.metaLabel}>{t("settings.company.country")}</div>
              <div className={styles.metaValue}>{company.country}</div>
            </div>
            <div>
              <div className={styles.metaLabel}>{t("settings.company.timezone")}</div>
              <div className={styles.metaValue}>{company.timezone}</div>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

