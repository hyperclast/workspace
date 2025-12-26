from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, List, Optional, Union
import hashlib
import pickle

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string
from django_rq.jobs import Job
from rq import get_current_job
from rq.exceptions import NoSuchJobError
import django_rq

from backend.utils import log_error, log_info, log_warning


def enqueue_task(
    func: Callable,
    queue_name: str,
    check_pending: Optional[bool] = True,
    schedule: Optional[datetime | timedelta] = None,
    *args,
    **kwargs,
) -> Job:
    if check_pending and is_func_in_pending_jobs(func, queue_name, *args, **kwargs):
        log_info("Skipping as still pending")
        return

    q = django_rq.get_queue(queue_name)
    job = None

    if isinstance(schedule, timedelta):
        job = q.enqueue_in(schedule, func, *args, **kwargs)

    elif isinstance(schedule, datetime):
        job = q.enqueue_at(schedule, func, *args, **kwargs)

    else:
        job = q.enqueue(func, *args, **kwargs)

    log_info("Enqueued %s", job)

    return job


def handle_task(
    func: Callable,
    queue_name: Optional[str] = None,
    check_pending: Optional[bool] = True,
    schedule: Optional[datetime | timedelta] = None,
    force_sync: Optional[bool] = False,
    *args,
    **kwargs,
) -> Job | Any:
    """Enqueus or runs the given func."""
    func_name = func.__name__

    try:
        if settings.JOB_RUNNER == "rq" and not force_sync:
            log_info("Enqueueing %s in queue %s", func_name, queue_name)
            return enqueue_task(
                func,
                queue_name,
                check_pending,
                schedule,
                *args,
                **kwargs,
            )

        else:
            log_info("Running %s in synchronous mode", func_name)
            return func(*args, **kwargs)

    except Exception as e:
        log_error("Error enqueueing/running %s: %s", func_name, e)


def task(
    queue_name: Optional[str] = None,
    default_check_pending: bool = True,
    default_schedule: Optional[Union[datetime, timedelta]] = None,
    default_force_sync: bool = False,
):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        def enqueue(
            *args,
            check_pending=default_check_pending,
            schedule=default_schedule,
            force_sync=default_force_sync,
            **kwargs,
        ):
            return handle_task(
                func,
                queue_name,
                check_pending,
                schedule,
                force_sync,
                *args,
                **kwargs,
            )

        wrapper.enqueue = enqueue
        return wrapper

    return decorator


def is_func_in_pending_jobs(func: Callable, queue_name: str, *args, **kwargs) -> bool:
    queue = django_rq.get_queue(queue_name)
    job_ids = _get_all_pending_job_ids(queue)
    if len(job_ids) == 0:
        return False

    functions = _get_func_in_jobs(q=queue, job_ids=job_ids)
    func_call_key = _make_func_call_key(func, *args, **kwargs)

    return func_call_key in functions


def _get_all_pending_job_ids(q: "DjangoRQ") -> List[str]:
    """Retrieves job IDs of queued, started, or scheduled jobs."""
    job_ids = []

    if q.count > 0:
        job_ids.extend(q.get_job_ids())
    if q.started_job_registry.count > 0:
        job_ids.extend(q.started_job_registry.get_job_ids())
    if q.scheduled_job_registry.count > 0:
        job_ids.extend(q.scheduled_job_registry.get_job_ids())

    return job_ids


def _get_func_in_jobs(q: "DjangoRQ", job_ids: List[str]) -> dict:
    """Returns functions currently in jobs."""
    functions_in_jobs = defaultdict(list)
    for job_obj in Job.fetch_many(job_ids, connection=q.connection):
        func_call_key = _make_func_call_key(job_obj.func, *job_obj.args, **job_obj.kwargs)
        functions_in_jobs[func_call_key].append(job_obj.id)
    return functions_in_jobs


def _make_func_call_key(func: Callable, *args, **kwargs) -> str:
    """Generates unique key based on the function and the args/kwargs it's called with."""
    params = args, kwargs
    serialized_params = pickle.dumps(params)
    hash = hashlib.sha1(f"{func.__name__}_{serialized_params}".encode())
    return hash.hexdigest()


def get_job_status(job_id: str, queue_name: str) -> str | None:
    try:
        q = django_rq.get_queue(queue_name)
        job = Job.fetch(job_id, connection=q.connection)
        return job.get_status(refresh=True)

    except NoSuchJobError:
        log_warning(f"Unable to find job {job_id} in queue {queue_name}")
        return


def is_job_id_pending(job_id: str, queue_name: str) -> bool:
    result = False
    status = get_job_status(job_id, queue_name)

    if status is not None:
        result = status in ["queued", "started", "scheduled"]

    return result


def wait_for_all_then_run(
    job_ids: List[str],
    queue_name_to_check: str,
    check_every: timedelta,
    final_task_path: str,
    final_task_args: Optional[list] = None,
    final_task_kwargs: Optional[dict] = None,
) -> None:
    """Checks if all jobs in `job_ids` are done before running final task."""
    log_info("Checking status of %d jobs in %s", len(job_ids), queue_name_to_check)
    has_pending = False

    for job_id in job_ids:
        if is_job_id_pending(job_id, queue_name_to_check):
            # At least one job is still pending/running
            has_pending = True
            break

    if has_pending:
        # Re-enqueue the current coordinator task to run after `schedule` interval
        job = get_current_job()
        num_retries = job.meta.get("num_retries", 0)
        first_retried_at = job.meta.get("first_retried_at", timezone.now())
        log_info("Retrying %d", num_retries + 1)

        # TODO:
        # Consider stopping re-enqueueing if:
        # - max retries is reached
        # - certain amount of time has already elapsed since `first_retried_at`

        re_enqueued_job = handle_task(
            wait_for_all_then_run,
            job.origin,
            check_pending=False,
            schedule=check_every,
            job_ids=job_ids,
            queue_name_to_check=queue_name_to_check,
            check_every=check_every,
            final_task_path=final_task_path,
            final_task_args=final_task_args,
            final_task_kwargs=final_task_kwargs,
        )
        re_enqueued_job.meta["num_retries"] = num_retries + 1
        re_enqueued_job.meta["first_retried_at"] = first_retried_at
        re_enqueued_job.save_meta()

    else:
        # Run the final task
        final_task = import_string(final_task_path)
        final_task_args = final_task_args or []
        final_task_kwargs = final_task_kwargs or {}
        final_task(
            *final_task_args,
            **final_task_kwargs,
        )
