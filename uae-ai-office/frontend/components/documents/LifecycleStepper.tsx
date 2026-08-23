"use client";

import { useTranslation } from "@/lib/i18n";
import clsx from "@/components/ui/clsx";
import type { DocumentPublic } from "@/lib/types";
import { getLifecycleSteps } from "./lifecycle";
import styles from "./LifecycleStepper.module.css";

export function LifecycleStepper({ document }: { document: DocumentPublic }) {
  const { t } = useTranslation();
  const steps = getLifecycleSteps(document);

  return (
    <div className={styles.stepper}>
      {steps.map((step, index) => (
        <div key={step.key} className={styles.stepWrap}>
          <div className={styles.step}>
            <span className={clsx(styles.dot, styles[step.state])}>
              {step.state === "done" ? (
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                  <path d="M1.5 5.2 3.8 7.5 8.5 2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : step.state === "error" ? (
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                  <path d="M2 2 8 8M8 2 2 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              ) : null}
            </span>
            <span className={clsx(styles.label, styles[`label-${step.state}`])}>{t(step.key)}</span>
          </div>
          {index < steps.length - 1 ? <span className={clsx(styles.connector, styles[`connector-${step.state}`])} /> : null}
        </div>
      ))}
    </div>
  );
}

