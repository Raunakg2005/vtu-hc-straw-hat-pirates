"""Sample 'legacy' payment service used to demo the scanner (deliberately quantum-vulnerable)."""
import hashlib

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
DEVICE_KEY = ec.generate_private_key(ec.SECP256R1())
SESSION_KEY = AESGCM.generate_key(bit_length=128)


def sign_token(claims):
    return jwt.encode(claims, SIGNING_KEY, algorithm="RS256")


def receipt_id(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
