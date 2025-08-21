"""Registry system for modular data collectors."""

from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class DataCollector(Protocol):
    """Protocol defining the interface for data collectors."""
    
    @abstractmethod
    def collect(self, url: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect data for the given URL."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources."""
        pass


@dataclass
class CollectorConfig:
    """Configuration for a data collector."""
    name: str
    enabled: bool
    settings: Dict[str, Any]
    dependencies: List[str] = None
    priority: int = 100


class CollectorRegistry:
    """Registry for managing data collectors."""
    
    def __init__(self):
        self._collectors: Dict[str, DataCollector] = {}
        self._configs: Dict[str, CollectorConfig] = {}
    
    def register_collector(self, name: str, collector: DataCollector, config: CollectorConfig):
        """Register a data collector."""
        self._collectors[name] = collector
        self._configs[name] = config
        logger.info(f"Registered collector: {name} (enabled={config.enabled}, priority={config.priority})")
    
    def get_enabled_collectors(self) -> List[str]:
        """Get list of enabled collector names in priority order."""
        enabled = [(name, config.priority) for name, config in self._configs.items() if config.enabled]
        return [name for name, _ in sorted(enabled, key=lambda x: x[1])]
    
    def get_collector(self, name: str) -> Optional[DataCollector]:
        """Get a specific collector by name."""
        return self._collectors.get(name)
    
    def collect_data(self, url: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run all enabled collectors and aggregate results."""
        results = {}
        
        for collector_name in self.get_enabled_collectors():
            if collector_name in self._collectors:
                try:
                    logger.debug(f"Running collector: {collector_name}")
                    collector_results = self._collectors[collector_name].collect(url, context)
                    results[collector_name] = collector_results
                except Exception as e:
                    logger.error(f"Collector {collector_name} failed: {e}")
                    results[collector_name] = {'error': str(e), 'success': False}
        
        return results
    
    def cleanup_all(self):
        """Cleanup all collectors."""
        for name, collector in self._collectors.items():
            try:
                collector.cleanup()
                logger.debug(f"Cleaned up collector: {name}")
            except Exception as e:
                logger.error(f"Failed to cleanup collector {name}: {e}")