"""Derive the exact RSA public key from rsa_key.p8 and write a ready-to-paste SQL file."""
from pathlib import Path

from cryptography.hazmat.primitives import serialization

p8 = Path("C:/CSPM_PROJECT/rsa_key.p8").read_bytes()
priv = serialization.load_pem_private_key(p8, password=None)
pub_pem = priv.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

body = "".join(l for l in pub_pem.splitlines() if "KEY" not in l)

# sanity: round-trip parse
serialization.load_pem_public_key(pub_pem.encode())

# compare with rsa_key.pub on disk
disk = "".join(l.strip() for l in Path("C:/CSPM_PROJECT/rsa_key.pub").read_text().splitlines() if "KEY" not in l and l.strip())
print("Matches rsa_key.pub:", disk == body)
print("Key length:", len(body))

sql = (
    "USE ROLE ACCOUNTADMIN;\n"
    f"ALTER USER YASHSNOW20 SET RSA_PUBLIC_KEY='{body}';\n"
    "DESC USER YASHSNOW20;\n"
)
Path("C:/CSPM_PROJECT/scripts/secondary_set_rsa_key.sql").write_text(sql, encoding="utf-8")
print("Wrote scripts/secondary_set_rsa_key.sql")
