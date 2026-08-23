import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { useTranslation } from "@/lib/i18n";
import clsx from "./clsx";
import styles from "./Field.module.css";

export function FieldWrapper({
  label,
  htmlFor,
  optional,
  hint,
  error,
  children,
}: {
  label?: string;
  htmlFor?: string;
  optional?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className={styles.field}>
      {label ? (
        <label className={styles.label} htmlFor={htmlFor}>
          {label} {optional ? <span className={styles.optional}>{t("common.optional")}</span> : null}
        </label>
      ) : null}
      {children}
      {error ? <span className={styles.error}>{error}</span> : hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref
) {
  return <input ref={ref} className={clsx(styles.control, className)} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, ...rest },
  ref
) {
  return <select ref={ref} className={clsx(styles.control, className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={clsx(styles.control, className)} {...rest} />;
  }
);

