from app.translation.secrets import SecretStore


class MemoryBackend:
    def __init__(self) -> None:
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_secret_store_uses_selected_backend():
    backend = MemoryBackend()
    store = SecretStore(backend=backend)

    store.set("deepl", "  private-key  ")
    assert store.get("deepl") == "private-key"

    store.delete("deepl")
    assert store.get("deepl") is None
