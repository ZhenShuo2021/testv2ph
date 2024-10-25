import sys
import logging  # noqa: F401
from viztracer import VizTracer

import v2dl  # noqa: F401


def run_with_viztracer():
    # 設定命令列參數
    sys.argv = [
        "profiler.py",
        "https://www.v2ph.com/album/Weekly-Big-Comic-Spirits-2016-No22-23",
        "--dry-run",
        "--bot",
        "drission",
    ]

    args, log_level = v2dl.utils.parse_arguments()
    config = ConfigManager().load()
    setup_logging(log_level, log_path=config.paths.system_log)
    logger = logging.getLogger(__name__)

    web_bot = get_bot(args.bot_type, config, args.terminate, logger)
    scraper = ScrapeManager(args.url, web_bot, args.dry_run, config, logger)
    scraper.start_scraping()
    main()


tracer = VizTracer(output_file="trace.json")
tracer.start()

try:
    run_with_viztracer()
finally:
    tracer.stop()
    tracer.save()

# {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X "+
# "10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10."
# "1.2 Safari/603.3.8', 'accept': 'text/html,application/xhtml"
# "+xml,application/xml;q=0.9,*/*;q=0.8', 'connection': "
# "'keep-alive', 'accept-charset': 'GB2312,utf-8;q=0.7,*;q=0.7'}"