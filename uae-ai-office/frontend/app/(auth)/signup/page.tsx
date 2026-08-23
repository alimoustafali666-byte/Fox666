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

export default function SignupPage() {
  const { signup } = useAuth();
  const { t } = useTranslation();
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup({ email, password, full_name: fullName, company_name: companyName });
    } catch (err) {
      setError(errorMessage(err, t("auth.signUp.genericError")));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardBody>
        <h1 className={formStyles.title}>{t("auth.signUp.title")}</h1>
        <p className={formStyles.subtitle}>{t("auth.signUp.subtitle")}</p>

        {error ? <ErrorBanner message={error} /> : null}

        <form className={formStyles.form} onSubmit={handleSubmit} style={{ marginTop: error ? 16 : 0 }}>
          <FieldWrapper label={t("auth.signUp.fullName")} htmlFor="full_name">
            <Input
              id="full_name"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t("auth.fullNamePlaceholder")}
            />
          </FieldWrapper>

          <FieldWrapper label={t("auth.signUp.companyName")} htmlFor="company_name">
            <Input
              id="company_name"
              autoComplete="organization"
              required
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder={t("auth.companyNamePlaceholder")}
            />
          </FieldWrapper>

          <FieldWrapper label={t("auth.signUp.workEmail")} htmlFor="email">
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

          <FieldWrapper label={t("auth.signUp.password")} htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
            />
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                marginTop: 6,
                fontSize: "var(--font-size-xs)",
                color: password.length >= 12 ? "var(--color-success)" : "var(--color-text-muted)",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  flexShrink: 0,
                  background: password.length >= 12 ? "var(--color-success)" : "var(--color-border-strong)",
                  transition: "background-color var(--transition-fast)",
                }}
              />
              {t("auth.signUp.passwordHint")}
            </span>
          </FieldWrapper>

          <Button type="submit" block loading={submitting}>
            {submitting ? t("auth.signUp.submitting") : t("auth.signUp.submit")}
          </Button>
        </form>

        <div className={formStyles.footer}>
          {t("auth.signUp.haveAccount")} <Link href="/login">{t("auth.signUp.signIn")}</Link>
        </div>
      </CardBody>
    </Card>
  );
}

