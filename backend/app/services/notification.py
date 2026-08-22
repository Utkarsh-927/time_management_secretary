from typing import Optional


def send_notification(
    title: str,
    message: Optional[str] = None
):
    """
    Send a local notification.

    For now, notifications are displayed in the
    application console. Later this service can be
    connected to a desktop notification or frontend.
    """

    print("\n")
    print("========================================")
    print("           🔔 NOTIFICATION")
    print("========================================")
    print(f"Title   : {title}")

    if message:
        print(f"Message : {message}")

    print("========================================")
    print("\n")

