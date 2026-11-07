"""Generates a VAPID key pair for browser push. Run once:  python scripts/generate_vapid.py
Copy the two lines into your .env (and into AWS Secrets Manager for production). Keep the private key secret."""
import base64

from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric import ec


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
print("VAPID_PRIVATE_KEY=" + b64(key.private_numbers().private_value.to_bytes(32, "big")))
print("VAPID_PUBLIC_KEY=" + b64(key.public_key().public_bytes(ser.Encoding.X962, ser.PublicFormat.UncompressedPoint)))
print("VAPID_SUBJECT=mailto:you@example.com")
