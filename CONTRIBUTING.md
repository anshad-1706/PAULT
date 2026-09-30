# Contributing to PAULT

Contributions are welcome. PAULT's V1 architecture and behavior are the baseline; keep changes focused and preserve its security and portability goals.

## Workflow

1. Fork the repository on GitHub.
2. Create a focused branch for your change.
3. Install the project and test dependencies with `python -m pip install -r requirements.txt` and `python -m pip install -e .`.
4. Run `python -m pytest -q` and describe the change and test results in your pull request.
5. Open a pull request from your branch and explain any user-visible or compatibility effects.

For security-sensitive changes, explain the threat or invariant addressed and add focused tests. Do not disclose a vulnerability in a public pull request; follow [SECURITY.md](SECURITY.md) instead.

Never commit secrets, credentials, private keys, vault files, personal data, plaintext exports, sensitive logs, local settings, virtual environments, or generated build output. Do not include real personal files in tests or screenshots. Test fixtures should use synthetic data.

Do not make changes to encryption, password handling, or the vault format without a clearly documented reason and careful review. Avoid unrelated dependency upgrades and preserve the existing `pault_core` package name.

Contributors retain appropriate attribution for their contributions. The project is licensed under GPL-3.0-or-later; see [LICENSE](LICENSE).