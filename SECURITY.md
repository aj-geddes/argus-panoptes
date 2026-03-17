# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in Argus Panoptes, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please send an email to the maintainers with the following information:

1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Impact assessment** -- what an attacker could achieve
4. **Affected versions** (if known)
5. **Suggested fix** (if you have one)

### What to expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours.
- **Assessment**: We will investigate and assess the severity within 5 business days.
- **Fix timeline**: Critical vulnerabilities will be patched within 7 days. Lower-severity issues will be addressed in the next scheduled release.
- **Credit**: We will credit you in the release notes (unless you prefer to remain anonymous).

## Security Practices

Argus Panoptes follows these security practices:

### Authentication

- API key authentication is available for ingestion endpoints (configured via `security.api_key_auth` in `config/argus.yaml` or the `ARGUS_API_KEY` environment variable)
- API keys are compared using constant-time comparison to prevent timing attacks
- Health check and documentation endpoints bypass authentication

### Rate Limiting

- Configurable per-client rate limiting on ingestion endpoints
- Prevents abuse and denial-of-service attacks on the ingestion pipeline

### Dependencies

- Dependencies are pinned to minimum versions in `pyproject.toml`
- `bandit` security scanning runs in CI on every pull request
- Dependencies should be regularly audited with `pip-audit`

### Docker

- Production Docker image runs as a non-root user (`argus`)
- Multi-stage build minimizes attack surface
- No secrets are baked into the image

### Configuration

- Secrets (API keys, database passwords) should be provided via environment variables, not committed to source control
- The `config/argus.yaml` file supports `${ENV_VAR}` interpolation for sensitive values
- The example config (`config/argus.example.yaml`) contains no real credentials

### Database

- SQLAlchemy parameterized queries prevent SQL injection
- Database credentials should be passed via `DATABASE_URL` environment variable in production
- Connection pooling with `pool_pre_ping` ensures stale connections are detected
