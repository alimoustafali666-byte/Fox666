"use client";

import { useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { authApi, ApiError } from "@/lib/api-client";
import { setAccessToken } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import formStyles from "../../AuthForm.module.css";

export default function InvitationPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { t } = useTranslation();
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await authApi.acceptInvitation(token, { full_name: fullName, password });
      setAccessToken(response.access_token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("auth.signIn.genericError"));
    } finally {
      setSubmitting(false);
    }
  }

  return <Card><CardBody><h1 className={formStyles.title}>{t("settings.team.acceptTitle")}</h1>
    {error ? <ErrorBanner message={error} /> : null}
    <form className={formStyles.form} onSubmit={handleSubmit}>
      <FieldWrapper label={t("settings.team.fullName")} htmlFor="full-name"><Input id="full-name" required value={fullName} onChange={(e) => setFullName(e.target.value)} /></FieldWrapper>
      <FieldWrapper label={t("settings.team.password")} htmlFor="password"><Input id="password" type="password" minLength={12} required value={password} onChange={(e) => setPassword(e.target.value)} /></FieldWrapper>
      <Button type="submit" block loading={submitting}>{t("settings.team.acceptButton")}</Button>
    </form>
  </CardBody></Card>;
}