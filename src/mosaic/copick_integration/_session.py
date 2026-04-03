"""Persistent copick session state shared across dialogs."""


class CopickSession:
    """Singleton that holds a copick root across dialog invocations.

    Dialogs use the session to pre-populate config/runs without re-connecting.
    Clicking Connect always reloads the root fresh (picks up external changes).
    """

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.config_path = None
        self.root = None

    def connect(self, config_path):
        """Load (or reload) a copick project from *config_path*.

        Always creates a fresh root so that data added by external tools
        since the last connect is visible.
        """
        from copick import from_file

        self.root = from_file(config_path)
        self.config_path = config_path
        return self.root

    def disconnect(self):
        self.root = None
        self.config_path = None

    @property
    def is_connected(self):
        return self.root is not None

    @property
    def runs(self):
        if self.root is None:
            return []
        return sorted(self.root.runs, key=lambda r: r.name.lower())
