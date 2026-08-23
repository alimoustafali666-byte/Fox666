"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth, errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import formStyles from "../AuthForm.module.css";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(errorMessage(err, t("auth.signIn.genericError")));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardBody>
        <h1 className={formStyles.title}>{t("auth.signIn.title")}</h1>
        <p className={formStyles.subtitle}>{t("auth.signIn.subtitle")}</p>

        {error ? <ErrorBanner message={error} /> : null}

        <form className={formStyles.form} onSubmit={handleSubmit} style={{ marginTop: error ? 16 : 0 }}>
          <FieldWrapper label={t("auth.signIn.workEmail")} htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("auth.emailPlaceholder")}
            />
          </FieldWrapper>

          <FieldWrapper label={t("auth.signIn.password")} htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
            />
          </FieldWrapper>

          <Button type="submit" block loading={submitting}>
            {submitting ? t("auth.signIn.submitting") : t("auth.signIn.submit")}
          </Button>
        </form>

        <div className={formStyles.footer}>
          {t("auth.signIn.noAccount")} <Link href="/signup">{t("auth.signIn.createOne")}</Link>
        </div>
      </CardBody>
    </Card>
  );
}

