# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it by emailing:
**security@affilync.com**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Measures

### Authentication & Authorization
- OAuth 2.0 for BigCommerce authorization
- JWT tokens with short expiration for session management
- HMAC-SHA256 signature verification for webhooks (X-BC-Webhook-HMAC-SHA256)

### Data Protection
- Fernet encryption (AES-128-CBC) for access tokens at rest
- PBKDF2 key derivation with 100,000 iterations
- TLS 1.3 for all data in transit
- No PII stored beyond what's necessary for operation

### API Security
- Rate limiting on all endpoints
- Input validation via Pydantic schemas
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via React's automatic escaping
- CORS restricted to BigCommerce and Affilync domains

### Infrastructure
- Render.com managed infrastructure
- Automatic security patches
- Environment variables for secrets (never in code)
- Secrets detection in pre-commit hooks

### Webhook Security
- HMAC-SHA256 signature verification (X-BC-Webhook-HMAC-SHA256 header)
- Timestamp validation to prevent replay attacks
- Webhook logging for audit trail

## Security Best Practices for Contributors

1. Never commit secrets, API keys, or credentials
2. Use environment variables for all sensitive configuration
3. Validate all user input
4. Use parameterized queries (handled by SQLAlchemy)
5. Keep dependencies updated
6. Run security scans before merging (bandit, detect-secrets)
