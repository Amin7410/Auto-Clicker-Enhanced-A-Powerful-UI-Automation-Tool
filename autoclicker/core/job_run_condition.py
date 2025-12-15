# core/job_run_condition.py
import time
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class JobContext:
    """
    Provides context information to JobRunCondition checks.
    """
    def __init__(self, run_count: int = 0, start_time: float = 0.0, job_name: str = ""):
        self.run_count = run_count 
        self.start_time = start_time 
        self.job_name = job_name


class JobRunCondition(ABC):
    """
    Abstract base class for conditions that control how long a Job runs.
    """
    def __init__(self, type: str, params: dict = None):
        if not isinstance(type, str) or not type:
             raise ValueError("JobRunCondition type must be a non-empty string.")
        self.type = type
        self.params = params or {}
        if not isinstance(self.params, dict):
             logger.warning(f"Params for condition type '{self.type}' is not a dict ({type(params)}). Using empty dict.")
             self.params = {}


    @abstractmethod
    def check_continue(self, context: JobContext) -> bool:
        """
        Checks if the Job should continue running the next loop iteration.

        Args:
            context (JobContext): Contextual information about the running job.

        Returns:
            bool: True if the job should continue, False if it should stop.
        """
        pass

    def reset(self):
        pass 

    def to_dict(self) -> dict:
        return {"type": self.type, "params": self.params}

    @classmethod
    def from_dict(cls, data: dict):

        if not isinstance(data, dict):
             raise ValueError("JobRunCondition data must be a dictionary.")
        condition_type = data.get("type")
        params = data.get("params", {})
        if not isinstance(condition_type, str) or not condition_type:
             logger.error(f"Invalid or missing 'type' in JobRunCondition data: {data}")
             raise ValueError("JobRunCondition data must contain a non-empty 'type' string.")

        if not isinstance(params, dict):
             logger.warning(f"Invalid 'params' type in JobRunCondition data ({type(params)}). Using empty dict.")
             params = {}
        return cls(condition_type, params) 

class InfiniteRunCondition(JobRunCondition):
    """ Job runs until manually stopped. """
    TYPE = "infinite"

    def __init__(self, params: dict = None):
        super().__init__(type=self.TYPE, params=params)

    def check_continue(self, context: JobContext) -> bool:
        """ An infinite condition always continues. """
        return True


class CountRunCondition(JobRunCondition):
    """ Job runs for a specified number of times. """
    TYPE = "count"

    def __init__(self, params: dict = None):
        super().__init__(type=self.TYPE, params=params)
        try:
            self.target_count = max(1, int(self.params.get("count", 1)))
            self.params["count"] = self.target_count
        except (ValueError, TypeError):
            logger.error(f"Invalid 'count' parameter for CountRunCondition: {self.params.get('count')}. Defaulting to 1.")
            self.target_count = 1
            self.params["count"] = 1 


    def check_continue(self, context: JobContext) -> bool:
        """ Continues as long as the run count is less than the target. """
        should_continue = context.run_count < self.target_count
        if not should_continue and context.run_count == self.target_count:
             logger.info(f"Job '{context.job_name}' stopping: Completed target run count ({self.target_count}).")
        return should_continue

class TimeRunCondition(JobRunCondition):
    """ Job runs for a specified duration. """
    TYPE = "time"

    def __init__(self, params: dict = None):
        super().__init__(type=self.TYPE, params=params)
        try:
            self.duration_seconds = max(0.1, float(self.params.get("duration", 60.0)))
            self.params["duration"] = self.duration_seconds
        except (ValueError, TypeError):
             logger.error(f"Invalid 'duration' parameter for TimeRunCondition: {self.params.get('duration')}. Defaulting to 60.0.")
             self.duration_seconds = 60.0
             self.params["duration"] = 60.0 


    def check_continue(self, context: JobContext) -> bool:
        """ Continues as long as the elapsed time is less than the duration. """
        if context.start_time == 0.0:
             logger.warning(f"Job '{context.job_name}': Start time is 0.0 in TimeRunCondition check. Cannot check duration.")
             return False 

        elapsed_time = time.monotonic() - context.start_time
        should_continue = elapsed_time < self.duration_seconds
        if not should_continue and elapsed_time >= self.duration_seconds:
             logger.info(f"Job '{context.job_name}' stopping: Reached target duration ({self.duration_seconds}s).")
        return should_continue

def create_job_run_condition(data: dict | None) -> JobRunCondition:
     """
     Factory function to create a JobRunCondition instance from a dictionary.
     Handles different types and provides a default InfiniteRunCondition for invalid input.

     Args:
         data (dict | None): The dictionary representation of the condition (e.g., from config).

     Returns:
         JobRunCondition: An instance of the appropriate JobRunCondition subclass.
     """
     if not isinstance(data, dict):
         logger.warning(f"Invalid data type for JobRunCondition factory: {type(data)}. Data: {data}. Falling back to Infinite.")
         return InfiniteRunCondition() 

     condition_type = data.get("type")
     params = data.get("params", {})

     if not isinstance(condition_type, str) or not condition_type:
         logger.warning(f"Missing or invalid 'type' in JobRunCondition data: {data}. Falling back to Infinite.")
         return InfiniteRunCondition() 

     try:
         if condition_type == InfiniteRunCondition.TYPE:
             return InfiniteRunCondition(params)
         elif condition_type == CountRunCondition.TYPE:
             return CountRunCondition(params)
         elif condition_type == TimeRunCondition.TYPE:
              return TimeRunCondition(params)

         else:
             logger.warning(f"Unknown JobRunCondition type '{condition_type}' in data: {data}. Falling back to Infinite.")
             return InfiniteRunCondition()

     except Exception as e:
         logger.error(f"Error creating JobRunCondition of type '{condition_type}' from data: {data}. Error: {e}.", exc_info=True)
         logger.warning("Falling back to InfiniteRunCondition due to creation error.")
         return InfiniteRunCondition()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger.info("--- JobRunCondition Test ---")

    cond_inf = create_job_run_condition(None)
    cond_count = create_job_run_condition({"type": "count", "params": {"count": 10}})
    cond_time = create_job_run_condition({"type": "time", "params": {"duration": 5.5}})
    cond_invalid_type = create_job_run_condition({"type": "unknown", "params": {}})
    cond_invalid_count = create_job_run_condition({"type": "count", "params": {"count": "abc"}})

    print(f"Created: {cond_inf}, {cond_count}, {cond_time}, {cond_invalid_type}, {cond_invalid_count}")

    context = JobContext(run_count=0, start_time=time.monotonic(), job_name="TestJob")

    print("\n--- Checking conditions ---")
    print(f"Infinite (run 0): {cond_inf.check_continue(context)}") 
    print(f"Count 10 (run 0): {cond_count.check_continue(context)}") 
    print(f"Time 5.5s (elapsed 0s): {cond_time.check_continue(context)}") 

    context_half_done = JobContext(run_count=5, start_time=time.monotonic() - 2.5, job_name="TestJob")
    print(f"Count 10 (run 5): {cond_count.check_continue(context_half_done)}") 
    print(f"Time 5.5s (elapsed 2.5s): {cond_time.check_continue(context_half_done)}") 

    context_finished_count = JobContext(run_count=10, start_time=time.monotonic() - 6.0, job_name="TestJob")
    print(f"Count 10 (run 10): {cond_count.check_continue(context_finished_count)}") 
    print(f"Time 5.5s (elapsed 6.0s): {cond_time.check_continue(context_finished_count)}") 

    print("\n--- Serialization Test ---")
    inf_dict = cond_inf.to_dict()
    count_dict = cond_count.to_dict()
    time_dict = cond_time.to_dict()

    print(f"Infinite dict: {inf_dict}")
    print(f"Count dict: {count_dict}")
    print(f"Time dict: {time_dict}")

    recreated_inf = create_job_run_condition(inf_dict)
    recreated_count = create_job_run_condition(count_dict)
    recreated_time = create_job_run_condition(time_dict)

    print("\n--- Deserialization Test ---")
    print(f"Recreated Infinite: {recreated_inf}")
    print(f"Recreated Count: {recreated_count}")
    print(f"Recreated Time: {recreated_time}")
    print(f"Recreated invalid count: {create_job_run_condition({'type': 'count', 'params': {'count': 'xyz'}})}")
