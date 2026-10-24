from __future__ import annotations

import os

import keyring
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError


class SecretStoreError(RuntimeError):
    pass


class SecretStore:
    """Store provider credentials in Windows Credential Manager through keyring."""

    def __init__(
        self,
        service_name: str = "LiveScreenTranslatorPro",
        backend: KeyringBackend | None = None,
    ) -> None:
        self.service_name = service_name
        if backend is not None:
            self.backend = backend
        elif os.name == "nt":
            # Frozen apps do not expose keyring's package entry points
            # reliably. Select the native backend explicitly on Windows.
            from keyring.backends.Windows import WinVaultKeyring

            self.backend = WinVaultKeyring()
        else:
            self.backend = keyring.get_keyring()

    def get(self, provider: str) -> str | None:
        try:
            return self.backend.get_password(self.service_name, f"{provider}_api_key")
        except (KeyringError, OSError, RuntimeError) as exc:
            raise SecretStoreError("Không thể đọc Windows Credential Manager.") from exc

    def set(self, provider: str, secret: str) -> None:
        if not secret.strip():
            return
        try:
            self.backend.set_password(
                self.service_name, f"{provider}_api_key", secret.strip()
            )
        except (KeyringError, OSError, RuntimeError) as exc:
            raise SecretStoreError("Không thể ghi Windows Credential Manager.") from exc

    def delete(self, provider: str) -> None:
        try:
            self.backend.delete_password(self.service_name, f"{provider}_api_key")
        except (KeyringError, OSError, RuntimeError) as exc:
            raise SecretStoreError("Không thể xóa credential đã lưu.") from exc
