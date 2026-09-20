from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.workers.queue import JobQueue, get_job_queue

SessionDep = Annotated[AsyncSession, Depends(get_session)]
QueueDep = Annotated[JobQueue, Depends(get_job_queue)]
