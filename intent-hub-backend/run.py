"""Intent Hub startup script."""
from intent_hub.app import init_app
from intent_hub.config import Config
from intent_hub.utils.logger import suppress_health_check_logs, logger

if __name__ == "__main__":
    logger.info("Initializing Intent Hub...")
    try:
        app = init_app()
        logger.info("Intent Hub initialized.")
    except Exception as e:
        logger.error(f"Component initialization failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    suppress_health_check_logs()
    logger.info(f"Starting Flask server: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )

