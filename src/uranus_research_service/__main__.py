import sys

import uvicorn

from uranus_research_service.app import create_app
from uranus_research_service.logging import configure_logging, logger


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "index":
        from uranus_research_service.index_cli import main as index_main

        index_main(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        from uranus_research_service.ground_truth_cli import main as benchmark_main

        benchmark_main(sys.argv[2:])
        return
    configure_logging()
    try:
        app = create_app()
    except (ValueError, OSError):
        logger.error("startup_failed", extra={"error_type": "invalid_configuration"})
        sys.exit(1)
    uvicorn.run(app, host="0.0.0.0", port=6338, access_log=False, log_config=None)


if __name__ == "__main__":
    main()
