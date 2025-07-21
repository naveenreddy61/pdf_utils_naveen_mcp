from . import server


def main():
    """Main entry point for the package."""
    # Call the main function from server.py directly since FastMCP handles async internally
    server.main()


# Optionally expose other important items at package level
__all__ = ['main', 'server']