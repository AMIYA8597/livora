# PHASE 20A — REAL-TIME MESSAGING KNOWN ISSUES & LIMITATIONS

**Date:** November 2026  
**System:** Flatmate Compatibility & Rental Marketplace  
**Subsystem:** Messaging & Real-Time Communication

---

## 1. Documented Operational Limitations & Mitigations

### 1.1 Standalone In-Memory Fallback vs. Redis Clustering
- **Behavior:** If `REDIS_URL` is unreachable or misconfigured, `DistributedEventBroker` falls back to in-memory event dispatch.
- **Impact:** In single-node staging or local testing, all real-time events function seamlessly. In multi-replica Kubernetes or ECS deployments without Redis, users connected to different replicas will not receive real-time push events until page reload or polling.
- **Mitigation:** Production deployments must specify a valid, managed Redis cluster (e.g. AWS ElastiCache, Redis Cloud, or Supabase Realtime).

### 1.2 Ephemeral Typing States
- **Behavior:** Typing indicators expire after 5 seconds and are kept in-memory.
- **Impact:** Typing state is not preserved across server restarts.
- **Mitigation:** Intentional design: typing indicators are ephemeral and do not warrant permanent database persistence.

### 1.3 Audio / Video Call Signaling
- **Behavior:** Phase 20A covers text messaging, group messaging, receipts, typing, presence, attachments, and safety controls. WebRTC signaling for peer-to-peer audio/video calls is planned for a subsequent phase.

### 1.4 Push Notifications (APNs / FCM)
- **Behavior:** Real-time in-app notifications and WebSocket `notification.created` events are fully operational. Mobile push notifications (Apple Push Notification Service / Firebase Cloud Messaging) are structured behind replaceable interfaces and will be enabled upon mobile app packaging.
