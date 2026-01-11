# Security Policy

## 🔒 Reporting a Vulnerability

We take the security of Iran Protest Map seriously. If you believe you have found a security vulnerability, please report it to us as described below.

**⚠️ Please do NOT report security vulnerabilities through public GitHub issues.**

### How to Report

1. **Email the maintainers directly** (check GitHub profiles for contact info)
2. Include the following information:
   - Type of issue (e.g., SQL injection, XSS, authentication bypass)
   - Full paths of source file(s) related to the issue
   - Location of the affected source code (tag/branch/commit or direct URL)
   - Step-by-step instructions to reproduce the issue
   - Proof-of-concept or exploit code (if possible)
   - Impact of the issue, including how an attacker might exploit it

### What to Expect

- **Acknowledgment**: We will acknowledge your report within 48 hours
- **Updates**: We will keep you informed of the progress toward a fix
- **Resolution**: We aim to resolve critical issues within 7 days
- **Credit**: We will credit you in the security advisory (unless you prefer anonymity)

## 🛡️ Security Best Practices for Contributors

### Never Commit Secrets

- API keys, tokens, or passwords
- Database credentials
- Private keys or certificates
- Any sensitive configuration

Use environment variables instead:

```python
# ✅ Good
api_key = os.getenv("API_KEY")

# ❌ Bad
api_key = "sk-1234567890abcdef"
```

### Validate All Input

- Sanitize user input on both frontend and backend
- Use parameterized queries for database operations
- Validate and escape data before rendering

### Keep Dependencies Updated

- Regularly update npm and pip packages
- Monitor security advisories for dependencies
- Use tools like `npm audit` and `pip-audit`

### Data Privacy

This project handles sensitive data related to protests and human rights. Extra care must be taken:

- Never log personally identifiable information (PII)
- Anonymize data where possible
- Follow data minimization principles
- Respect the privacy and safety of sources

## 🔐 Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | ✅ Supported       |
| < 1.0   | ❌ Not supported   |

## 📋 Security Checklist for PRs

Before submitting a PR, ensure:

- [ ] No secrets or credentials are committed
- [ ] User input is properly validated
- [ ] SQL queries use parameterized statements
- [ ] No debug/console.log statements with sensitive data
- [ ] Dependencies are up to date
- [ ] New endpoints have appropriate authentication

## 🙏 Acknowledgments

We appreciate the security research community's efforts in responsibly disclosing vulnerabilities. Contributors who report valid security issues will be acknowledged in our security advisories.

---

Thank you for helping keep Iran Protest Map and its users safe!

