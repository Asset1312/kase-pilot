"""Application entry point."""

from kase_pilot.core.version import APP_NAME, __version__


def main() -> None:
    """Run the application."""
    print(f"{APP_NAME} v{__version__}")
    print("System initialized successfully.")


if __name__ == "__main__":
    main()
