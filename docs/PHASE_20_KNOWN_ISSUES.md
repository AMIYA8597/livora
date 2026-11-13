# Phase 20 Known Issues & Non-Blocking Observations

**Phase:** Phase 20 — Enterprise-Grade Staging Infrastructure  
**Date:** November 14, 2026  
**Auditor:** Quality Assurance Lead & Site Reliability Engineer  
**Classification:** No blocking, critical, or high-severity vulnerabilities remain.

---

## 1. Non-Blocking Technical Observations

The following low-severity items have been documented for optimization during Phase 21 (Production Launch Engineering):

### 1. SQLAlchemy `datetime.utcnow()` Deprecation Warnings in Legacy Tests
- **Observation:** Certain legacy tests in `test_auth.py` and `test_phase17_e2e_integration.py` trigger SQLAlchemy deprecation warnings regarding `datetime.datetime.utcnow()` being deprecated in Python 3.12+.
- **Impact:** Zero functional impact. Python 3.11/3.13 continues to execute the queries without interruption.
- **Remediation Plan (Phase 21):** Standardize all timestamp column default factories to `datetime.now(timezone.utc)`.

### 2. Node.js Typeless Module Reparsing Warning in Web Unit Tests
- **Observation:** When running `node --experimental-strip-types --test tests/*.test.ts` directly, Node outputs a warning that `apps/web/package.json` does not specify `"type": "module"`.
- **Impact:** Minor overhead during direct local test invocation; zero impact on the Next.js bundle or runtime.
- **Remediation Plan (Phase 21):** Add `"type": "module"` to `apps/web/package.json` and adjust build script flags.

### 3. Google Cloud Secret Manager Binding Boundary
- **Observation:** Automatic creation of secret resources in GCP Secret Manager requires explicit project IAM permissions. In automated CI/CD runners, GitHub Actions repository secrets are injected as runtime environment variables.
- **Impact:** Standard operational behavior; secrets remain masked and protected from git.

---

## 2. Risk Assessment Summary

- **Critical Vulnerabilities:** 0
- **High Vulnerabilities:** 0
- **Medium Bugs:** 0
- **Low Enhancements:** 3
- **Staging Release Readiness:** **UNBLOCKED / READY FOR PRODUCTION LAUNCH PHASE 21**
