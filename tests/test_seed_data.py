"""Tests for the seed data service."""

from sqlalchemy import select, func

from app.models.incident import Incident, IncidentStatus
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.services.seed_data import seed_database, SEED_INCIDENTS


async def test_seed_populates_empty_db(db_session):
    """Seed creates incidents when DB is empty."""
    count_before = (await db_session.execute(select(func.count(Incident.id)))).scalar_one()
    assert count_before == 0

    await seed_database(db_session)

    count_after = (await db_session.execute(select(func.count(Incident.id)))).scalar_one()
    assert count_after == len(SEED_INCIDENTS)


async def test_seed_skips_non_empty_db(db_session):
    """Seed does not add data if incidents already exist."""
    await seed_database(db_session)
    first_count = (await db_session.execute(select(func.count(Incident.id)))).scalar_one()

    await seed_database(db_session)
    second_count = (await db_session.execute(select(func.count(Incident.id)))).scalar_one()

    assert first_count == second_count


async def test_seed_creates_tickets_for_dispatched(db_session):
    """Dispatched seed incidents get associated tickets."""
    await seed_database(db_session)

    dispatched_count = sum(1 for d in SEED_INCIDENTS if d["ticket"] is not None)
    ticket_count = (await db_session.execute(select(func.count(Ticket.id)))).scalar_one()
    assert ticket_count == dispatched_count


async def test_seed_creates_notifications(db_session):
    """Seed incidents with notifications get notification records."""
    await seed_database(db_session)

    expected = sum(len(d["notifications"]) for d in SEED_INCIDENTS)
    actual = (await db_session.execute(select(func.count(Notification.id)))).scalar_one()
    assert actual == expected


async def test_seed_incident_statuses(db_session):
    """Seed creates a mix of submitted and dispatched incidents."""
    await seed_database(db_session)

    result = await db_session.execute(select(Incident))
    incidents = list(result.scalars().all())

    statuses = {i.status for i in incidents}
    assert IncidentStatus.SUBMITTED in statuses
    assert IncidentStatus.DISPATCHED in statuses
