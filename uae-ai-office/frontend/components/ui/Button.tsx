"use client";

import type { ButtonHTMLAttributes } from "react";
import clsx from "./clsx";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  loading?: boolean;
}

export function buttonClassName(variant: ButtonVariant = "primary", size: ButtonSize = "md", block = false) {
  return clsx(styles.btn, styles[variant], styles[size], block && styles.block);
}

export function Button({
  variant = "primary",
  size = "md",
  block = false,
  loading = false,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button className={clsx(buttonClassName(variant, size, block), className)} disabled={disabled || loading} {...rest}>
      {children}
    </button>
  );
}

