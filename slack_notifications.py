import logging

logger = logging.getLogger(__name__)

def notify_slack(message: str) -> None:
    """
    Placeholder function for Slack notifications.
    Currently just prints the message to the terminal.
    
    Args:
        message (str): The message to be sent to Slack
    """
    logger.info(f"[SLACK STUB] {message}") 