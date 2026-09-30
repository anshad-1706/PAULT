# PAULT Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately using GitHub's private vulnerability reporting feature for this repository: https://github.com/anshad-1706/PAULT/security/advisories/new. Do not report vulnerabilities through public issues or discussions.

When reporting, include the affected version and platform, a concise description of impact, and reproduction steps that do not expose real passwords, keys, vaults, or personal files. Coordinate public disclosure with the maintainers after a fix or mitigation is available. No response-time commitment is currently published.

## Scope and limitations

PAULT uses Argon2id and AES-256-GCM for password-based key derivation and authenticated encryption. The implementation details are documented in [docs/SECURITY.md](docs/SECURITY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). PAULT cannot guarantee plaintext erasure from memory, operating-system storage, external applications, or temporary video playback files.
