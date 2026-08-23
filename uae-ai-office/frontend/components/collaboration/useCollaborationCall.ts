"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { collaborationApi } from "@/lib/api-client";
import type { CollaborationSocketEvent } from "@/lib/collaboration-socket";
import type { CallType } from "@/lib/types";

// Real 1:1 WebRTC calling -- peer-to-peer audio/video with the backend
// acting only as a signaling relay (see app/modules/collaboration/ws.py)
// and call-session/participant bookkeeping (see the REST /calls
// endpoints). Deliberately 1:1 only: a group call needs a media server
// (SFU) to fan out N streams, which is out of scope for this MVP (see
// the Step 18 report) -- callers with 3+ active members never get this
// hook wired up by the page.
//
// NAT traversal here uses a public STUN server only, no TURN. This is
// enough for most direct peer-to-peer paths but will fail behind
// symmetric NATs/restrictive firewalls -- a production deployment needs
// a TURN server (e.g. coturn) added to ICE_SERVERS.
const ICE_SERVERS: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];

export type CallPhase = "idle" | "outgoing" | "incoming" | "connecting" | "active" | "ended" | "declined" | "error";

interface IncomingCall {
  callSessionId: string;
  fromUserId: string;
  callType: CallType;
  offer: RTCSessionDescriptionInit;
}

interface UseCollaborationCallArgs {
  peerUserId: string | null;
  subscribeSocket: (listener: (event: CollaborationSocketEvent) => void) => () => void;
  sendSocket: (payload: Record<string, unknown>) => void;
}

export function useCollaborationCall({ peerUserId, subscribeSocket, sendSocket }: UseCollaborationCallArgs) {
  const [phase, setPhase] = useState<CallPhase>("idle");
  const [callType, setCallType] = useState<CallType>("voice");
  const [callSessionId, setCallSessionId] = useState<string | null>(null);
  const [incoming, setIncoming] = useState<IncomingCall | null>(null);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [muted, setMuted] = useState(false);
  const [cameraOff, setCameraOff] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const pendingCandidatesRef = useRef<RTCIceCandidateInit[]>([]);
  // Tracks which call sessions have already had a remote answer applied.
  // A signalingState check alone is race-prone: setRemoteDescription is
  // asynchronous, so two near-simultaneous deliveries of the same
  // answer (e.g. a dev-only double-effect, or a genuine duplicate
  // relay) can both read "have-local-offer" before either's operation
  // has actually applied -- this flag is set synchronously instead, so
  // a second delivery is always rejected regardless of timing.
  const answeredSessionsRef = useRef<Set<string>>(new Set());

  const cleanup = useCallback(() => {
    pcRef.current?.close();
    pcRef.current = null;
    pendingCandidatesRef.current = [];
    answeredSessionsRef.current.clear();
    localStream?.getTracks().forEach((track) => track.stop());
    setLocalStream(null);
    setRemoteStream(null);
    setMuted(false);
    setCameraOff(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localStream]);

  const reset = useCallback(() => {
    cleanup();
    setPhase("idle");
    setCallSessionId(null);
    setIncoming(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleanup]);

  const createPeerConnection = useCallback(
    (targetUserId: string, sessionId: string): RTCPeerConnection => {
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          sendSocket({
            type: "webrtc_ice_candidate",
            call_session_id: sessionId,
            target_user_id: targetUserId,
            payload: event.candidate.toJSON(),
          });
        }
      };
      pc.ontrack = (event) => {
        setRemoteStream(event.streams[0] ?? null);
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") setPhase("active");
        if (pc.connectionState === "failed" || pc.connectionState === "disconnected") setPhase("ended");
      };
      pcRef.current = pc;
      return pc;
    },
    [sendSocket]
  );

  const startCall = useCallback(
    async (type: CallType, conversationId: string) => {
      if (!peerUserId) return;
      setError(null);
      setCallType(type);
      setPhase("outgoing");
      try {
        const session = await collaborationApi.startCall(conversationId, type);
        setCallSessionId(session.id);
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: type === "video" });
        setLocalStream(stream);
        const pc = createPeerConnection(peerUserId, session.id);
        stream.getTracks().forEach((track) => pc.addTrack(track, stream));
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        sendSocket({
          type: "webrtc_offer",
          call_session_id: session.id,
          target_user_id: peerUserId,
          payload: { sdp: offer, call_type: type },
        });
      } catch {
        setError("mediaPermissionError");
        setPhase("error");
      }
    },
    [peerUserId, sendSocket, createPeerConnection]
  );

  const answerCall = useCallback(async () => {
    if (!incoming) return;
    setError(null);
    setPhase("connecting");
    try {
      await collaborationApi.respondToCall(incoming.callSessionId, "joined");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: incoming.callType === "video" });
      setLocalStream(stream);
      const pc = createPeerConnection(incoming.fromUserId, incoming.callSessionId);
      stream.getTracks().forEach((track) => pc.addTrack(track, stream));
      await pc.setRemoteDescription(incoming.offer);
      for (const candidate of pendingCandidatesRef.current) {
        await pc.addIceCandidate(candidate);
      }
      pendingCandidatesRef.current = [];
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSocket({
        type: "webrtc_answer",
        call_session_id: incoming.callSessionId,
        target_user_id: incoming.fromUserId,
        payload: { sdp: answer },
      });
      setCallSessionId(incoming.callSessionId);
      setCallType(incoming.callType);
      setIncoming(null);
    } catch {
      setError("mediaPermissionError");
      setPhase("error");
    }
  }, [incoming, sendSocket, createPeerConnection]);

  const declineCall = useCallback(async () => {
    if (!incoming) return;
    try {
      await collaborationApi.respondToCall(incoming.callSessionId, "declined");
    } catch {
      // Best-effort -- the incoming banner is dismissed regardless.
    }
    setIncoming(null);
    setPhase("idle");
  }, [incoming]);

  const hangUp = useCallback(async () => {
    const sessionId = callSessionId;
    reset();
    if (sessionId) {
      try {
        await collaborationApi.endCall(sessionId);
      } catch {
        // Best-effort -- the local call view is already torn down.
      }
    }
  }, [callSessionId, reset]);

  const toggleMute = useCallback(() => {
    if (!localStream) return;
    const next = !muted;
    localStream.getAudioTracks().forEach((track) => {
      track.enabled = !next;
    });
    setMuted(next);
  }, [localStream, muted]);

  const toggleCamera = useCallback(() => {
    if (!localStream) return;
    const next = !cameraOff;
    localStream.getVideoTracks().forEach((track) => {
      track.enabled = !next;
    });
    setCameraOff(next);
  }, [localStream, cameraOff]);

  useEffect(() => {
    const unsubscribe = subscribeSocket((event: CollaborationSocketEvent) => {
      if (event.type === "webrtc_offer") {
        const payload = event.payload as { sdp: RTCSessionDescriptionInit; call_type?: CallType };
        setIncoming({
          callSessionId: event.call_session_id,
          fromUserId: event.from_user_id,
          callType: payload.call_type ?? "voice",
          offer: payload.sdp,
        });
        setPhase("incoming");
        return;
      }
      if (event.type === "webrtc_answer") {
        const payload = event.payload as { sdp: RTCSessionDescriptionInit };
        // Guard against a duplicate/late-delivered answer for a call
        // that has already had one applied -- checked and set
        // synchronously (not via signalingState, which only updates
        // once setRemoteDescription's async operation actually runs,
        // leaving a window where two near-simultaneous deliveries could
        // both pass the check and the second would throw).
        if (pcRef.current && event.call_session_id === callSessionId && !answeredSessionsRef.current.has(event.call_session_id)) {
          answeredSessionsRef.current.add(event.call_session_id);
          pcRef.current.setRemoteDescription(payload.sdp).then(() => {
            for (const candidate of pendingCandidatesRef.current) {
              pcRef.current?.addIceCandidate(candidate);
            }
            pendingCandidatesRef.current = [];
          });
          setPhase("connecting");
        }
        return;
      }
      if (event.type === "webrtc_ice_candidate") {
        const candidate = event.payload as RTCIceCandidateInit;
        if (pcRef.current?.remoteDescription) {
          pcRef.current.addIceCandidate(candidate).catch(() => undefined);
        } else {
          pendingCandidatesRef.current.push(candidate);
        }
      }
    });
    return unsubscribe;
  }, [subscribeSocket, callSessionId]);

  useEffect(() => {
    return () => {
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    phase,
    callType,
    incoming,
    localStream,
    remoteStream,
    muted,
    cameraOff,
    error,
    startCall,
    answerCall,
    declineCall,
    hangUp,
    toggleMute,
    toggleCamera,
  };
}

