# Security, Privacy & Compliance Architecture

**Status:** Enforced  
**Standards:** OWASP Top 10, GDPR, CCPA, SOC2 Type II Alignment  

---

## 1. Threat Modeling & Attack Vectors

| Threat Vector | Mitigation Strategy |
| :--- | :--- |
| **Rental Deposit Scams & Ghost Listings** | Mandatory address verification, phone number check, landlord title deed check, and automated duplicate image detection. |
| **Identity Theft / Impersonation** | Multi-factor verification (Govt ID + live selfie check), verified student/corporate email validation. |
| **Harassment & Stalking** | In-app messaging masking phone numbers/emails, instant blocking, automated keyword flagging, reporting queue. |
| **Data Scraping & PII Harvesting** | Strict Redis rate limiting on listing queries, obfuscation of precise street addresses until viewing confirmation. |
| **SQL Injection & Insecure Deserialization** | Parameterized queries via SQLAlchemy async ORM, strict Pydantic v2 data validation schemas. |

---

## 2. Authentication & Authorization Architecture

### 2.1 Password Hashing & Key Derivation
- Passwords hashed using **bcrypt** with work factor cost **12**.
- Password complexity requirements: Minimum 8 characters, at least 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special symbol.

### 2.2 JWT Token Lifecycle
- **Access Tokens**: Short-lived (60 minutes), signed with `HS256` or `RS256` asymmetric keys. Payload contains `sub` (User UUID), `role` (`seeker`, `owner`, `admin`), and `jti` (Token ID).
- **Refresh Tokens**: Long-lived (30 days), stored hashed in Redis with family rotation to prevent replay attacks.
- **Revocation**: Instant logout revokes refresh token families and adds access token `jti` to Redis blacklist with TTL matching token expiration.

### 2.3 Role-Based Access Control (RBAC)
- **Seeker**: Can browse listings, view public profiles, send applications, join flatmate groups, exchange messages.
- **Owner / Landlord**: Can create/manage property listings, view full applicant credentials, approve/reject tenancies.
- **Moderator / Admin**: Can review flagged content, suspend accounts, access audit logs.

---

## 3. PostgreSQL Row-Level Security (RLS)

PostgreSQL RLS ensures that database tenants cannot accidentally or maliciously query data belonging to other entities even in the event of an application logic bug.

```sql
-- Enable RLS on conversations and messages
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;

-- Policy: Only conversation participants can read conversation messages
CREATE POLICY user_read_conversation_messages ON messages
    FOR SELECT
    USING (
        conversation_id IN (
            SELECT id FROM conversations WHERE EXISTS (
                SELECT 1 FROM conversation_participants 
                WHERE conversation_participants.conversation_id = conversations.id 
                AND conversation_participants.user_id = current_setting('app.current_user_id')::UUID
            )
        )
    );

-- Policy: Only applicant or listing owner can view rental application
CREATE POLICY applicant_or_owner_view_application ON applications
    FOR SELECT
    USING (
        applicant_id = current_setting('app.current_user_id')::UUID
        OR property_id IN (
            SELECT id FROM properties 
            WHERE owner_id = current_setting('app.current_user_id')::UUID
        )
    );
```

---

## 4. Verification Documents & PII Protection

1. **Storage Isolation**:
   - Government identification cards, passports, and proof-of-income documents are saved exclusively to the private `flatmate-private-docs` bucket.
   - Buckets are locked down with strict AWS S3 / MinIO IAM policies; no public internet reads permitted.
2. **Encryption at Rest & In Transit**:
   - Server-Side Encryption with KMS (SSE-KMS) or AES-256 for all stored documents.
   - TLS 1.3 enforced for all external and intra-service communication.
3. **Time-Limited Access**:
   - Authorized admins and automated verification workers access documents via presigned URLs strictly expiring after 5 minutes.
4. **Data Minimization & Deletion**:
   - Verification documents are automatically scrubbed 90 days after verification approval.

---

## 5. Anti-Abuse & Rate Limiting

Redis Token Bucket rate limiting:
- `/api/v1/auth/login`: 5 requests per minute per IP.
- `/api/v1/auth/register`: 3 requests per hour per IP.
- `/api/v1/messaging/*`: 60 requests per minute per authenticated user.
- `/api/v1/properties/search/*`: 120 requests per minute per IP.
