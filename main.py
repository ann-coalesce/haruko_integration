import logging, sys
import get_risk_margin_data
import get_risk_margin_concurrent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)sZ %(levelname)s %(message)s",
    stream=sys.stdout,
)

# get_risk_margin_data.main()
get_risk_margin_concurrent.main()