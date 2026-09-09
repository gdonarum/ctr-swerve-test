"""TLS trust configuration for corporate proxies such as Zscaler.

Zscaler (and similar TLS-inspecting proxies) re-sign HTTPS traffic with a
corporate root CA that Python does not trust out of the box. Two ways to fix it,
both supported here:

1. **CA bundle file** — set ``AICODER_CA_BUNDLE`` (or the standard
   ``REQUESTS_CA_BUNDLE`` / ``SSL_CERT_FILE`` / ``CURL_CA_BUNDLE``) to a PEM file
   containing the proxy's root certificate (or a full bundle).
2. **System trust store** — set ``AICODER_SYSTEM_CERTS=1`` (or ``--system-certs``)
   to trust whatever the operating system trusts, which is where IT usually
   installs the Zscaler certificate. This uses the optional ``truststore``
   package (``pip install truststore``); if it isn't installed we say so.

``requests`` (GitLab) uses the CA bundle via ``verify=`` (``requests_verify``);
the OpenAI SDK uses it through a custom HTTP client built in ``llm.py`` (whose
type is tied to the installed SDK). The system-store injection patches Python's
SSL globally, so it covers both.
"""

from __future__ import annotations

from typing import Union

from aicoder.config import Config

_system_certs_injected = False


class CertError(Exception):
    """A problem configuring TLS trust (e.g. system certs requested but unavailable)."""


def apply_system_certs(config: Config) -> bool:
    """If requested, make Python trust the OS certificate store. Idempotent.

    Returns True if the system store is now in use. Raises CertError if the user
    asked for it but ``truststore`` is not installed.
    """
    global _system_certs_injected
    if not config.use_system_certs:
        return False
    if _system_certs_injected:
        return True
    try:
        import truststore  # optional dependency
    except ImportError as exc:
        raise CertError(
            "System certificate trust was requested (AICODER_SYSTEM_CERTS / "
            "--system-certs) but the 'truststore' package is not installed. "
            "Run: pip install truststore"
        ) from exc
    truststore.inject_into_ssl()
    _system_certs_injected = True
    return True


def requests_verify(config: Config) -> Union[str, bool]:
    """The value to pass as ``verify=`` to ``requests``."""
    if config.ca_bundle:
        return config.ca_bundle
    return True
