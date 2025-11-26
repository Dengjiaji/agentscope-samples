#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Environment Variable Configuration Loader
Supports loading configuration parameters from .env file and provides default values
"""

import os
from dataclasses import field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict


def load_env_file(env_file_path: str = None) -> Dict[str, str]:
    """
    Load .env file

    Args:
        env_file_path: .env file path, if None then search in project root directory

    Returns:
        Environment variable dictionary
    """
    env_vars = {}

    # Determine .env file path
    if env_file_path is None:
        # Search in project root directory
        project_root = Path(__file__).parent.parent.parent
        env_file_path = project_root / ".env"
    else:
        env_file_path = Path(env_file_path)

    # Load if file exists
    if env_file_path.exists():
        try:
            with open(env_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comment lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse key-value pairs
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Remove quotes
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]

                        env_vars[key] = value
        except Exception as e:
            print(f"⚠️ Failed to load .env file: {e}")

    return env_vars


def get_env_value(
    key: str,
    default: Any = None,
    value_type: type = str,
    env_vars: Dict[str, str] = None,
) -> Any:
    """
    Get environment variable value with type conversion support

    Args:
        key: Environment variable name
        default: Default value
        value_type: Expected data type
        env_vars: Environment variable dictionary, if None then get from system environment variables

    Returns:
        Converted value
    """
    # Priority: get from passed env_vars, then from system environment variables
    if env_vars is not None:
        value = env_vars.get(key)
    else:
        value = os.getenv(key)

    if value is None or value == "":
        return default

    # Type conversion
    try:
        if value_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif value_type == int:
            return int(value)
        elif value_type == float:
            return float(value)
        elif value_type == list:
            # Assume comma-separated string
            return [item.strip() for item in value.split(",") if item.strip()]
        else:
            return value
    except (ValueError, TypeError):
        print(
            f"⚠️ Environment variable {key} value '{value}' cannot be converted to {value_type.__name__}, using default value",
        )
        return default


class MultiDayConfig:
    """Multi-day strategy configuration class"""

    def __init__(self, env_file_path: str = None):
        """Initialize configuration"""
        self.env_vars = load_env_file(env_file_path)
        self.load_config()

    def load_config(self):
        """Load configuration parameters"""
        # Basic configuration
        self.tickers = get_env_value(
            "TICKERS",
            default=[],
            value_type=list,
            env_vars=self.env_vars,
        )
        self.output_dir = get_env_value(
            "OUTPUT_DIR",
            default="./analysis_results_logs",
            env_vars=self.env_vars,
        )
        self.verbose = get_env_value(
            "VERBOSE",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )

        # Run mode configuration
        self.mode = get_env_value(
            "MODE",
            default="signal",
            env_vars=self.env_vars,
        )
        if self.mode not in ["signal", "portfolio"]:
            print(
                f"⚠️ Invalid run mode: {self.mode}, using default value 'signal'",
            )
            self.mode = "signal"

        # Portfolio mode configuration
        self.initial_cash = get_env_value(
            "INITIAL_CASH",
            default=100000.0,
            value_type=float,
            env_vars=self.env_vars,
        )
        self.margin_requirement = get_env_value(
            "MARGIN_REQUIREMENT",
            default=0.0,
            value_type=float,
            env_vars=self.env_vars,
        )

        # Date configuration
        self.start_date = get_env_value(
            "START_DATE",
            default=None,
            env_vars=self.env_vars,
        )
        self.end_date = get_env_value(
            "END_DATE",
            default=None,
            env_vars=self.env_vars,
        )

        # Feature switches
        self.disable_communications = get_env_value(
            "DISABLE_COMMUNICATIONS",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.disable_notifications = get_env_value(
            "DISABLE_NOTIFICATIONS",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.disable_data_prefetch = get_env_value(
            "DISABLE_DATA_PREFETCH",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.enable_okr = get_env_value(
            "ENABLE_OKR",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.show_reasoning = get_env_value(
            "SHOW_REASONING",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.dry_run = get_env_value(
            "DRY_RUN",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )

        # Numeric configuration
        self.max_comm_cycles = get_env_value(
            "MAX_COMM_CYCLES",
            default=3,
            value_type=int,
            env_vars=self.env_vars,
        )

        # Use default values if dates are not set
        if not self.end_date:
            self.end_date = datetime.now().strftime("%Y-%m-%d")

        if not self.start_date:
            end_date_obj = datetime.strptime(self.end_date, "%Y-%m-%d")
            self.start_date = (end_date_obj - timedelta(days=30)).strftime(
                "%Y-%m-%d",
            )

    def override_with_args(self, args):
        """Override environment variable configuration with command line arguments"""
        if hasattr(args, "tickers") and args.tickers:
            self.tickers = [
                ticker.strip().upper()
                for ticker in args.tickers.split(",")
                if ticker.strip()
            ]

        if hasattr(args, "mode") and args.mode:
            if args.mode in ["signal", "portfolio"]:
                self.mode = args.mode
            else:
                print(
                    f"⚠️ Invalid run mode: {args.mode}, keeping current value '{self.mode}'",
                )

        if hasattr(args, "initial_cash") and args.initial_cash:
            self.initial_cash = args.initial_cash

        if hasattr(args, "margin_requirement") and args.margin_requirement:
            self.margin_requirement = args.margin_requirement

        if hasattr(args, "start_date") and args.start_date:
            self.start_date = args.start_date

        if hasattr(args, "end_date") and args.end_date:
            self.end_date = args.end_date

        if hasattr(args, "output_dir") and args.output_dir:
            self.output_dir = args.output_dir

        if (
            hasattr(args, "disable_communications")
            and args.disable_communications
        ):
            self.disable_communications = args.disable_communications

        if (
            hasattr(args, "disable_notifications")
            and args.disable_notifications
        ):
            self.disable_notifications = args.disable_notifications

        if (
            hasattr(args, "disable_data_prefetch")
            and args.disable_data_prefetch
        ):
            self.disable_data_prefetch = args.disable_data_prefetch

        if hasattr(args, "enable_okr") and args.enable_okr:
            self.enable_okr = args.enable_okr

        if hasattr(args, "show_reasoning") and args.show_reasoning:
            self.show_reasoning = args.show_reasoning

        if hasattr(args, "dry_run") and args.dry_run:
            self.dry_run = args.dry_run

        if hasattr(args, "verbose") and args.verbose:
            self.verbose = args.verbose

        if hasattr(args, "max_comm_cycles") and args.max_comm_cycles:
            self.max_comm_cycles = args.max_comm_cycles


class LiveTradingConfig:
    """Live trading system configuration class"""

    tickers: list[str] = field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    date: str | None = None
    max_comm_cycles: int = 2
    force_run: bool = False
    base_dir: str | None = None
    disable_communications: bool = False
    disable_notifications: bool = False

    def __init__(self, env_file_path: str = None):
        """Initialize configuration"""
        self.env_vars = load_env_file(env_file_path)
        self.load_config()

    def load_config(self):
        """Load configuration parameters"""
        # Basic configuration
        self.tickers = get_env_value(
            "TICKERS",
            default=[],
            value_type=list,
            env_vars=self.env_vars,
        )
        self.base_dir = get_env_value(
            "LIVE_BASE_DIR",
            default=None,
            env_vars=self.env_vars,
        )

        # Date configuration
        self.backfill_start_date = get_env_value(
            "BACKFILL_START_DATE",
            default="2025-01-01",
            env_vars=self.env_vars,
        )
        self.target_date = get_env_value(
            "TARGET_DATE",
            default=None,
            env_vars=self.env_vars,
        )

        # Feature switches
        self.force_run = get_env_value(
            "FORCE_RUN",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )

        # Numeric configuration
        self.max_comm_cycles = get_env_value(
            "LIVE_MAX_COMM_CYCLES",
            default=2,
            value_type=int,
            env_vars=self.env_vars,
        )

        self.disable_communications = get_env_value(
            "DISABLE_COMMUNICATIONS",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.disable_notifications = get_env_value(
            "DISABLE_NOTIFICATIONS",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )

    def override_with_args(self, args):
        """Override environment variable configuration with command line arguments"""
        if hasattr(args, "tickers") and args.tickers:
            self.tickers = [
                ticker.strip().upper()
                for ticker in args.tickers.split(",")
                if ticker.strip()
            ]

        if hasattr(args, "base_dir") and args.base_dir:
            self.base_dir = args.base_dir

        if hasattr(args, "start_date") and args.start_date:
            self.backfill_start_date = args.start_date

        if hasattr(args, "date") and args.date:
            self.target_date = args.date

        if hasattr(args, "force_run") and args.force_run:
            self.force_run = args.force_run

        if hasattr(args, "max_comm_cycles") and args.max_comm_cycles:
            self.max_comm_cycles = args.max_comm_cycles


class LiveThinkingFundConfig:
    """Live trading system configuration class"""

    tickers: list[str] = field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    date: str | None = None
    max_comm_cycles: int = 2
    force_run: bool = False
    base_dir: str | None = None
    disable_communications: bool = False
    disable_notifications: bool = False

    def __init__(self, env_file_path: str = None):
        """Initialize configuration"""
        self.env_vars = load_env_file(env_file_path)
        self.load_config()

    def load_config(self):
        """Load configuration parameters"""
        # Basic configuration
        self.tickers = get_env_value(
            "TICKERS",
            default=[],
            value_type=list,
            env_vars=self.env_vars,
        )
        self.base_dir = get_env_value(
            "LIVE_BASE_DIR",
            default=None,
            env_vars=self.env_vars,
        )

        # Run mode configuration (new)
        self.mode = get_env_value(
            "MODE",
            default="signal",
            env_vars=self.env_vars,
        )
        if self.mode not in ["signal", "portfolio"]:
            print(
                f"⚠️ Invalid run mode: {self.mode}, using default value 'signal'",
            )
            self.mode = "signal"

        # Portfolio mode configuration (new)
        self.initial_cash = get_env_value(
            "INITIAL_CASH",
            default=100000.0,
            value_type=float,
            env_vars=self.env_vars,
        )
        self.margin_requirement = get_env_value(
            "MARGIN_REQUIREMENT",
            default=0.0,
            value_type=float,
            env_vars=self.env_vars,
        )

        # Date configuration
        self.start_date = get_env_value(
            "START_DATE",
            default=None,
            env_vars=self.env_vars,
        )
        self.end_date = get_env_value(
            "END_DATE",
            default=None,
            env_vars=self.env_vars,
        )

        # Use default values if dates are not set
        if not self.end_date:
            self.end_date = datetime.now().strftime("%Y-%m-%d")

        if not self.start_date:
            end_date_obj = datetime.strptime(self.end_date, "%Y-%m-%d")
            self.start_date = (end_date_obj - timedelta(days=30)).strftime(
                "%Y-%m-%d",
            )

        # Feature switches
        self.force_run = get_env_value(
            "FORCE_RUN",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.pause_before_trade = get_env_value(
            "PAUSE_BEFORE_TRADE",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )

        # Numeric configuration
        self.max_comm_cycles = get_env_value(
            "LIVE_MAX_COMM_CYCLES",
            default=2,
            value_type=int,
            env_vars=self.env_vars,
        )

        self.disable_communications = get_env_value(
            "DISABLE_COMMUNICATIONS",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )
        self.disable_notifications = get_env_value(
            "DISABLE_NOTIFICATIONS",
            default=False,
            value_type=bool,
            env_vars=self.env_vars,
        )

    def override_with_args(self, args):
        """Override environment variable configuration with command line arguments"""
        if hasattr(args, "tickers") and args.tickers:
            self.tickers = [
                ticker.strip().upper()
                for ticker in args.tickers.split(",")
                if ticker.strip()
            ]

        if hasattr(args, "base_dir") and args.base_dir:
            self.base_dir = args.base_dir

        if hasattr(args, "start_date") and args.start_date:
            self.start_date = args.start_date

        if hasattr(args, "end_date") and args.end_date:
            self.end_date = args.end_date

        if hasattr(args, "date") and args.date:
            self.target_date = args.date

        if hasattr(args, "force_run") and args.force_run:
            self.force_run = args.force_run

        if hasattr(args, "max_comm_cycles") and args.max_comm_cycles:
            self.max_comm_cycles = args.max_comm_cycles

        if hasattr(args, "config_name") and args.config_name:
            self.config_name = args.config_name

        # Portfolio mode parameter override (new)
        if hasattr(args, "mode") and args.mode:
            self.mode = args.mode

        if hasattr(args, "initial_cash") and args.initial_cash is not None:
            self.initial_cash = args.initial_cash

        if (
            hasattr(args, "margin_requirement")
            and args.margin_requirement is not None
        ):
            self.margin_requirement = args.margin_requirement

        if hasattr(args, "pause_before_trade") and args.pause_before_trade:
            self.pause_before_trade = args.pause_before_trade


if __name__ == "__main__":
    # Test configuration loading
    print("\nTesting multi-day strategy configuration:")
    multi_config = MultiDayConfig()
    print(f"  Default stocks: {multi_config.tickers}")
    print(f"  Output directory: {multi_config.output_dir}")
    print(f"  Max communication cycles: {multi_config.max_comm_cycles}")

    print("\nTesting Live trading configuration:")
    live_config = LiveTradingConfig()
    print(f"  Default stocks: {live_config.tickers}")
    print(f"  Backfill start date: {live_config.backfill_start_date}")
    print(f"  Max communication cycles: {live_config.max_comm_cycles}")
