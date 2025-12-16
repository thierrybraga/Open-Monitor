# Config package
from .parallel_nvd_config import ParallelNVDConfig, ConfigurationManager
from .rate_limiter_config import RateLimiterConfig
from .scheduler_config import SchedulerConfig

def get_consolidated_configs(env: str | None = None) -> dict:
    return {
        'scheduler': SchedulerConfig.to_dict(),
        'rate_limiter': RateLimiterConfig.to_dict(),
        'parallel_nvd': ParallelNVDConfig.from_env().to_dict(),
    }

__all__ = ['ParallelNVDConfig', 'ConfigurationManager', 'RateLimiterConfig', 'SchedulerConfig', 'get_consolidated_configs']
