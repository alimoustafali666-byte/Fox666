"use client";

import { useEffect, useRef } from "react";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import type { CallType } from "@/lib/types";
import type { CallPhase } from "./useCollaborationCall";
import styles from "./CallPanel.module.css";

interface CallPanelProps {
  phase: CallPhase;
  callType: CallType;
  peerName: string;
  localStream: MediaStream | null;
  remoteStream: MediaStream | null;
  muted: boolean;
  cameraOff: boolean;
  onAnswer: () => void;
  onDecline: () => void;
  onHangUp: () => void;
  onToggleMute: () => void;
  onToggleCamera: () => void;
}

export function CallPanel({
  phase,
  callType,
  peerName,
  localStream,
  remoteStream,
  muted,
  cameraOff,
  onAnswer,
  onDecline,
  onHangUp,
  onToggleMute,
  onToggleCamera,
}: CallPanelProps) {
  const { t } = useTranslation();
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const remoteAudioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (localVideoRef.current) localVideoRef.current.srcObject = localStream;
  }, [localStream]);

  useEffect(() => {
    if (callType === "video" && remoteVideoRef.current) remoteVideoRef.current.srcObject = remoteStream;
    if (callType === "voice" && remoteAudioRef.current) remoteAudioRef.current.srcObject = remoteStream;
  }, [remoteStream, callType]);

  if (phase === "idle") return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.panel}>
        <div className={styles.peerName}>{peerName}</div>
        <div className={styles.status}>
          {phase === "outgoing" ? t("messages.calls.ringing") : null}
          {phase === "incoming" ? t("messages.calls.incomingCall", { name: peerName, type: t(callType === "video" ? "messages.calls.incomingVideo" : "messages.calls.incomingVoice") }) : null}
          {phase === "connecting" ? t("messages.calls.connecting") : null}
          {phase === "active" ? t("messages.calls.active") : null}
          {phase === "ended" ? t("messages.calls.ended") : null}
          {phase === "declined" ? t("messages.calls.declined") : null}
          {phase === "error" ? t("messages.calls.mediaPermissionError") : null}
        </div>

        {callType === "video" && (phase === "active" || phase === "connecting") ? (
          <div className={styles.videoGrid}>
            <video ref={remoteVideoRef} className={styles.remoteVideo} autoPlay playsInline />
            <video ref={localVideoRef} className={styles.localVideo} autoPlay playsInline muted />
          </div>
        ) : (
          <audio ref={remoteAudioRef} autoPlay />
        )}

        <div className={styles.controls}>
          {phase === "incoming" ? (
            <>
              <Button variant="primary" onClick={onAnswer}>
                {t("messages.calls.answerButton")}
              </Button>
              <Button variant="danger" onClick={onDecline}>
                {t("messages.calls.declineButton")}
              </Button>
            </>
          ) : phase === "active" || phase === "connecting" || phase === "outgoing" ? (
            <>
              <Button variant="secondary" onClick={onToggleMute}>
                {muted ? t("messages.calls.unmuteButton") : t("messages.calls.muteButton")}
              </Button>
              {callType === "video" ? (
                <Button variant="secondary" onClick={onToggleCamera}>
                  {cameraOff ? t("messages.calls.cameraOnButton") : t("messages.calls.cameraOffButton")}
                </Button>
              ) : null}
              <Button variant="danger" onClick={onHangUp}>
                {t("messages.calls.hangUpButton")}
              </Button>
            </>
          ) : (
            <Button variant="secondary" onClick={onHangUp}>
              {t("common.close")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

