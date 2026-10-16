import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


def pytest_addoption(parser):
    parser.addoption(
        "--mode",
        choices=["replay", "record", "live"],
        default="replay",
        help="evaluation suites: replay recorded answers (default), record new ones, or call the models live",
    )
