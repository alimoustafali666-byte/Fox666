"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { authApi, ApiError, setAccessToken } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { formatDateTime } from "@/lib/i18n/format";
import type { InvitationPreview } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import formStyles from "../../AuthForm.module.css";
import styles from "./Invite.module.css";

/** The invitation is loaded before the form renders because the two
 *  cases behind one link need different forms: an address with no
 *  account yet chooses a name and a new password, while an address that
 *  already has an account proves ownership of it with that account's
 *  existing password (the backend verifies it -- holding the link is not
 *  by itself authority over an account that already existed). Guessing
 *  wrong would mean asking someone to "create" a password that is then
 *  rejected, so the server is asked first. */
export default function InvitationPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { t, locale } = useTranslation();

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setPreview(await authApi.previewInvitation(token));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : t("settings.team.acceptInvalid"));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const existingAccount = preview?.requires_existing_password ?? false;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await authApi.acceptInvitation(token, {
        password,
        // Deliberately omitted for an existing account: an invitation
        // must not be able to rewrite that user's profile, and the
        // server ignores it there anyway.
        ...(existingAccount ? {} : { full_name: fullName }),
      });
      setAccessToken(response.access_token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.signIn.genericError"));
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardBody>
          <LoadingBlock label={t("settings.team.acceptLoading")} />
        </CardBody>
      </Card>
    );
  }

  if (loadError || !preview) {
    return (
      <Card>
        <CardBody>
          <h1 className={formStyles.title}>{t("settings.team.acceptInvalidTitle")}</h1>
          <p className={formStyles.subtitle}>{loadError ?? t("settings.team.acceptInvalid")}</p>
          <div className={formStyles.footer}>
            <Link href="/login">{t("settings.team.acceptGoToSignIn")}</Link>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <h1 className={formStyles.title}>
          {t("settings.team.acceptTitleFor", { company: preview.company_name })}
        </h1>
        <p className={formStyles.subtitle}>
          {existingAccount
            ? t("settings.team.acceptExistingSubtitle", { email: preview.email })
            : t("settings.team.acceptNewSubtitle", { email: preview.email })}
        </p>

        <dl className={styles.summary}>
          <div className={styles.summaryRow}>
            <dt>{t("settings.team.columns.email")}</dt>
            <dd>{preview.email}</dd>
          </div>
          <div className={styles.summaryRow}>
            <dt>{t("settings.team.columns.role")}</dt>
            <dd>{t(`common.roles.${preview.role}`)}</dd>
          </div>
          <div className={styles.summaryRow}>
            <dt>{t("settings.team.invitationExpires")}</dt>
            <dd>{formatDateTime(locale, preview.expires_at)}</dd>
          </div>
        </dl>

        {error ? <ErrorBanner message={error} /> : null}

        <form className={formStyles.form} onSubmit={handleSubmit} style={{ marginTop: 16 }}>
          {existingAccount ? null : (
            <FieldWrapper label={t("settings.team.fullName")} htmlFor="full-name">
              <Input
                id="full-name"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </FieldWrapper>
          )}

          <FieldWrapper
            label={
              existingAccount ? t("settings.team.existingPassword") : t("settings.team.password")
            }
            htmlFor="password"
            hint={
              existingAccount
                ? t("settings.team.existingPasswordHint")
                : t("settings.team.passwordHint")
            }
          >
            <Input
              id="password"
              type="password"
              autoComplete={existingAccount ? "current-password" : "new-password"}
              minLength={12}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
            />
          </FieldWrapper>

          <Button type="submit" block loading={submitting}>
            {existingAccount
              ? t("settings.team.acceptJoinButton")
              : t("settings.team.acceptButton")}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
