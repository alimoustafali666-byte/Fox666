import styles from "./ErrorBanner.module.css";

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className={styles.banner} role="alert">
      <svg className={styles.icon} width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.4" />
        <path d="M8 4.5V8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="8" cy="11" r="0.9" fill="currentColor" />
      </svg>
      <span>{message}</span>
    </div>
  );
}

