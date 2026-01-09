
import time
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class ComponentMetrics:
    """Metrics for a single component/operation."""
    name: str
    latency_seconds: float = 0.0
    call_count: int = 0
    error_count: int = 0
    tokens_input: int = 0
    tokens_output: int = 0

    @property
    def tokens_per_second(self) -> float:
        if self.latency_seconds > 0:
            return self.tokens_output / self.latency_seconds
        return 0.0


@dataclass
class PipelineMetrics:
    """Aggregated metrics for a complete pipeline execution."""
    request_id: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    components: Dict[str, ComponentMetrics] = field(default_factory=dict)
    action: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

    @property
    def total_latency(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def total_tokens_output(self) -> int:
        return sum(c.tokens_output for c in self.components.values())

    @property
    def total_tokens_input(self) -> int:
        return sum(c.tokens_input for c in self.components.values())

    @property
    def tokens_per_second(self) -> float:
        if self.total_latency > 0:
            return self.total_tokens_output / self.total_latency
        return 0.0

    def add_component(self, name: str, latency: float,
                      tokens_input: int = 0, tokens_output: int = 0,
                      error: bool = False):
        if name not in self.components:
            self.components[name] = ComponentMetrics(name=name)

        comp = self.components[name]
        comp.latency_seconds += latency
        comp.call_count += 1
        comp.tokens_input += tokens_input
        comp.tokens_output += tokens_output
        if error:
            comp.error_count += 1

    def finalize(self):
        self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "total_latency_seconds": round(self.total_latency, 4),
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "tokens_per_second": round(self.tokens_per_second, 2),
            "action": self.action,
            "success": self.success,
            "error_message": self.error_message,
            "components": {
                name: {
                    "latency_seconds": round(c.latency_seconds, 4),
                    "call_count": c.call_count,
                    "error_count": c.error_count,
                    "tokens_input": c.tokens_input,
                    "tokens_output": c.tokens_output,
                    "tokens_per_second": round(c.tokens_per_second, 2),
                }
                for name, c in self.components.items()
            }
        }

    def log_summary(self):
        """Log a summary of the metrics."""
        summary = self.to_dict()
        logger.info(f"Pipeline Metrics Summary: {summary}")

        # Print formatted output
        print(f"\n{'='*60}")
        print(f"PIPELINE METRICS - Request: {self.request_id}")
        print(f"{'='*60}")
        print(f"Total Latency: {self.total_latency:.4f} seconds")
        print(f"Total Tokens (in/out): {self.total_tokens_input}/{self.total_tokens_output}")
        print(f"Tokens/second: {self.tokens_per_second:.2f}")
        print(f"Action: {self.action}")
        print(f"Success: {self.success}")

        print(f"\n{'Component Breakdown':^60}")
        print(f"{'-'*60}")
        for name, comp in self.components.items():
            pct = (comp.latency_seconds / self.total_latency * 100) if self.total_latency > 0 else 0
            print(f"  {name}:")
            print(f"    Latency: {comp.latency_seconds:.4f}s ({pct:.1f}%)")
            print(f"    Calls: {comp.call_count}, Errors: {comp.error_count}")
            if comp.tokens_output > 0:
                print(f"    Tokens: {comp.tokens_input}/{comp.tokens_output} @ {comp.tokens_per_second:.2f} tok/s")
        print(f"{'='*60}\n")


class MetricsCollector:
    """Thread-safe metrics collector with context management."""

    _local = threading.local()
    _global_stats: Dict[str, list] = defaultdict(list)
    _lock = threading.Lock()

    @classmethod
    def start_pipeline(cls, request_id: str) -> PipelineMetrics:
        """Start tracking a new pipeline execution."""
        metrics = PipelineMetrics(request_id=request_id)
        cls._local.current_metrics = metrics
        return metrics

    @classmethod
    def get_current(cls) -> Optional[PipelineMetrics]:
        """Get the current pipeline metrics context."""
        return getattr(cls._local, 'current_metrics', None)

    @classmethod
    def end_pipeline(cls) -> Optional[PipelineMetrics]:
        """End the current pipeline and store stats."""
        metrics = cls.get_current()
        if metrics:
            metrics.finalize()
            with cls._lock:
                cls._global_stats['pipelines'].append(metrics.to_dict())
            cls._local.current_metrics = None
        return metrics

    @classmethod
    @contextmanager
    def measure(cls, component_name: str, tokens_input: int = 0):
        """Context manager to measure a component's execution."""
        start = time.time()
        error = False
        tokens_output = 0

        try:
            result_holder = {'tokens_output': 0}
            yield result_holder
            tokens_output = result_holder.get('tokens_output', 0)
        except Exception as e:
            error = True
            raise
        finally:
            latency = time.time() - start
            metrics = cls.get_current()
            if metrics:
                metrics.add_component(
                    name=component_name,
                    latency=latency,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    error=error
                )

    @classmethod
    def get_global_stats(cls) -> Dict[str, Any]:
        """Get aggregated statistics across all pipelines."""
        with cls._lock:
            pipelines = cls._global_stats['pipelines']
            if not pipelines:
                return {"message": "No pipeline data collected yet"}

            total_latencies = [p['total_latency_seconds'] for p in pipelines]
            return {
                "total_requests": len(pipelines),
                "avg_latency_seconds": sum(total_latencies) / len(total_latencies),
                "min_latency_seconds": min(total_latencies),
                "max_latency_seconds": max(total_latencies),
                "success_rate": sum(1 for p in pipelines if p['success']) / len(pipelines),
            }


def measure_latency(component_name: str):
    """Decorator to measure function execution latency."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with MetricsCollector.measure(component_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def measure_llm_call(component_name: str):
    """Decorator for LLM calls that extracts token usage."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            error = False
            tokens_input = 0
            tokens_output = 0

            try:
                result = func(*args, **kwargs)
                # Extract token usage from OpenAI response
                if hasattr(result, 'usage'):
                    tokens_input = result.usage.prompt_tokens
                    tokens_output = result.usage.completion_tokens
                return result
            except Exception as e:
                error = True
                raise
            finally:
                latency = time.time() - start
                metrics = MetricsCollector.get_current()
                if metrics:
                    metrics.add_component(
                        name=component_name,
                        latency=latency,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        error=error
                    )
        return wrapper
    return decorator
