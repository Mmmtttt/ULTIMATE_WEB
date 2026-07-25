"""
Self-signed SSL certificate management.

Generates and persists self-signed certificates for local HTTPS.
Certificates are stored under APP_CONFIG_DIR/ssl/.

The cryptography library is imported lazily so that platforms without
it (e.g. Android Chaquopy) can still import this module as long as
certificate generation is not triggered.
"""

from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from core.config_paths import APP_CONFIG_DIR


SSL_DIR_NAME = "ssl"
CERT_FILENAME = "cert.pem"
KEY_FILENAME = "key.pem"
CERT_VALIDITY_DAYS = 3650  # ~10 years

_cryptography_available: Optional[bool] = None


def _check_cryptography() -> bool:
    global _cryptography_available
    if _cryptography_available is not None:
        return _cryptography_available
    try:
        import cryptography  # noqa: F401
        _cryptography_available = True
    except Exception:
        _cryptography_available = False
    return _cryptography_available


def get_ssl_dir() -> str:
    """Return the absolute path to the SSL certificate directory."""
    return os.path.abspath(os.path.join(APP_CONFIG_DIR, SSL_DIR_NAME))


def get_cert_path() -> str:
    return os.path.join(get_ssl_dir(), CERT_FILENAME)


def get_key_path() -> str:
    return os.path.join(get_ssl_dir(), KEY_FILENAME)


def _collect_san_names() -> List[str]:
    """Collect Subject Alternative Names for the certificate."""
    names = {"localhost", "127.0.0.1", "0.0.0.0"}

    try:
        hostname = socket.gethostname()
        if hostname:
            names.add(hostname)
    except Exception:
        pass

    try:
        fqdn = socket.getfqdn()
        if fqdn:
            names.add(fqdn)
    except Exception:
        pass

    try:
        _, _, ip_addresses = socket.gethostbyname_ex(socket.gethostname())
        for ip in ip_addresses:
            if ip:
                names.add(ip)
    except Exception:
        pass

    return sorted(names)


def _looks_like_ip(value: str) -> bool:
    if not value:
        return False
    parts = value.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return True
    return False


def _generate_private_key():
    """Generate a 2048-bit RSA private key."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


def _generate_self_signed_cert(private_key, san_names: List[str]):
    """Generate a self-signed X.509 certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "ULTIMATE_WEB"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ULTIMATE_WEB"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Self-Signed"),
    ])

    now = datetime.now(timezone.utc)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=CERT_VALIDITY_DAYS))
    )

    if san_names:
        san_entries = []
        for name in san_names:
            if _looks_like_ip(name):
                try:
                    from ipaddress import ip_address
                    san_entries.append(x509.IPAddress(ip_address(name)))
                except Exception:
                    san_entries.append(x509.DNSName(name))
            else:
                san_entries.append(x509.DNSName(name))
        cert_builder = cert_builder.add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )

    cert = cert_builder.sign(private_key, hashes.SHA256())
    return cert


def _write_pem_files(cert, private_key, cert_path: str, key_path: str) -> None:
    """Write certificate and private key to PEM files."""
    from cryptography.hazmat.primitives import serialization

    os.makedirs(os.path.dirname(cert_path), exist_ok=True)

    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    with open(cert_path, "wb") as f:
        f.write(cert_pem)

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(key_path, "wb") as f:
        f.write(key_pem)


def cert_files_exist(cert_path: Optional[str] = None, key_path: Optional[str] = None) -> bool:
    """Check if both certificate and key files exist."""
    cp = cert_path or get_cert_path()
    kp = key_path or get_key_path()
    return os.path.isfile(cp) and os.path.isfile(kp)


def generate_self_signed_cert(cert_path: Optional[str] = None,
                              key_path: Optional[str] = None) -> Tuple[str, str]:
    """
    Generate a self-signed certificate and write it to disk.

    Returns (cert_path, key_path).
    Raises RuntimeError if the cryptography library is not available.
    """
    if not _check_cryptography():
        raise RuntimeError("cryptography library is not available; cannot generate SSL certificate")

    cp = cert_path or get_cert_path()
    kp = key_path or get_key_path()

    os.makedirs(os.path.dirname(cp), exist_ok=True)

    private_key = _generate_private_key()
    san_names = _collect_san_names()
    cert = _generate_self_signed_cert(private_key, san_names)
    _write_pem_files(cert, private_key, cp, kp)
    return cp, kp


def ensure_ssl_cert(cert_path: Optional[str] = None,
                    key_path: Optional[str] = None,
                    auto_generate: bool = True) -> Optional[Tuple[str, str]]:
    """
    Ensure SSL certificate files exist.

    If files already exist, return their paths.
    If auto_generate is True and files are missing, generate them.
    Returns None if certificates cannot be provided.
    """
    cp = cert_path or get_cert_path()
    kp = key_path or get_key_path()

    if cert_files_exist(cp, kp):
        return cp, kp

    if not auto_generate:
        return None

    if not _check_cryptography():
        return None

    try:
        return generate_self_signed_cert(cp, kp)
    except Exception:
        return None


def get_ssl_context_tuple(cert_path: Optional[str] = None,
                          key_path: Optional[str] = None,
                          auto_generate: bool = True) -> Optional[Tuple[str, str]]:
    """
    Return a (cert_path, key_path) tuple suitable for Flask ssl_context.

    Returns None if SSL is not available.
    """
    return ensure_ssl_cert(cert_path, key_path, auto_generate)
