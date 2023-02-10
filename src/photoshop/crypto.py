import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


SALT = b"Adobe Photoshop"


class EncryptDecrypt(object):
    def __init__(
        self,
        password: bytes,
        salt: bytes = SALT,
        iterations: int = 1000,
        length: int = 24,
    ):
        backend = default_backend()
        self.kdf = PBKDF2HMAC(
            algorithm=hashes.SHA1(),
            length=length,
            salt=salt,
            iterations=iterations,
            backend=backend,
        )
        key = self.kdf.derive(password)
        iv = b"\x00" * 8  # Always zeros.
        self.cipher = Cipher(algorithms.TripleDES(key), modes.CBC(iv), backend)
        self.padding = padding.PKCS7(algorithms.TripleDES.block_size)

    def encrypt(self, message: bytes) -> bytes:
        padder = self.padding.padder()
        padded_message = padder.update(message) + padder.finalize()
        encryptor = self.cipher.encryptor()
        return encryptor.update(padded_message) + encryptor.finalize()

    def decrypt(self, token: bytes) -> bytes:
        decryptor = self.cipher.decryptor()
        padded_message = decryptor.update(token) + decryptor.finalize()
        unpadder = self.padding.unpadder()
        return unpadder.update(padded_message) + unpadder.finalize()
