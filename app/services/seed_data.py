"""Seed data for development — pre-populates the database with sample incidents.

Only runs when APP_ENV=development and the incidents table is empty.
All triage data is from real Claude Haiku API calls captured on 2026-04-09.
Also seeds Langfuse with synthetic LLM traces matching the triage results so the
observability dashboard is populated on first container build.
"""

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident, IncidentStatus, Severity
from app.pipeline.dispatch import dispatch_incident

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed incident data — captured from real Claude Haiku triage calls
# ---------------------------------------------------------------------------
SEED_INCIDENTS = [
    {
        "reporter_name": "Maria Chen",
        "reporter_email": "maria.chen@example.com",
        "description": (
            "Payment gateway returning HTTP 502 errors during checkout. "
            "All customers affected since 14:30 UTC. Stripe webhook handler "
            "appears to be timing out. Error rate jumped from 0.1% to 45% in "
            "the last 15 minutes. Checkout completion rate dropped to near zero."
        ),
        "severity": Severity.P1,
        "category": "payment-processing",
        "affected_component": "Spree::Payment, Stripe webhook handler, payment gateway integration",
        "technical_summary": (
            "The incident shows a critical payment processing failure where HTTP 502 errors "
            "are being returned during checkout, with error rates spiking from 0.1% to 45% "
            "since 14:30 UTC. The primary indicator points to the Stripe webhook handler "
            "timing out, which would cause payment processing to hang and ultimately fail "
            "with gateway errors. In a Solidus/Spree payment architecture, webhooks are "
            "essential for async payment confirmation and settlement. When the webhook "
            "handler times out, it blocks payment confirmation flow, causing checkout "
            "completion to stall. The 502 errors suggest the application server is hitting "
            "resource exhaustion or hanging processes, likely due to unresolved webhook "
            "requests waiting indefinitely. This is a complete checkout failure affecting "
            "all customers attempting to pay.\n\n"
            "The payment processing pipeline in Spree relies on PaymentCreate.new().build "
            "and @payment.process! calls in the payments controller. If the underlying "
            "gateway communication (via Stripe webhooks) is timing out, the entire payment "
            "processing chain becomes unresponsive, causing the server to return 502 errors "
            "to waiting checkout requests."
        ),
        "root_cause_hypothesis": (
            "Stripe webhook handler is timing out or hanging, likely due to: "
            "(1) Webhook processing code blocking indefinitely on external I/O, "
            "(2) Database connection pool exhaustion causing webhook database operations "
            "to hang, (3) Upstream Stripe API latency causing timeout cascades, or "
            "(4) Recent deployment introducing a synchronous operation in webhook handling "
            "that should be async. The timeout in the webhook handler is consuming "
            "application server processes/threads, eventually leading to 502 errors when "
            "all available workers are blocked."
        ),
        "suggested_assignee": "payments-team",
        "confidence": 0.92,
        "recommended_actions": [
            "Immediately check Stripe webhook handler logs for timeout errors and stack traces - look for hanging requests or stuck threads",
            "Verify database connection pool status and ensure connections are not exhausted (check active connections, wait queue depth)",
            "Check application server worker/thread pool utilization - confirm workers are blocked on webhook processing",
            "Review recent deployments to payment/webhook code in the last 2 hours for any synchronous operations introduced in webhook handlers",
            "Check Stripe API status and latency metrics - confirm Stripe is responding normally",
            "Implement circuit breaker or timeout wrapper around Stripe webhook calls to prevent indefinite hangs",
            "Temporarily disable webhook processing with feature flag if root cause cannot be identified quickly, and manually reconcile payments from Stripe API",
            "Scale up application workers as temporary mitigation while investigating",
            "Query Spree::Payment records created in last 30 min to identify stuck payment states (checkout without confirmation)",
        ],
        "related_files": [
            {"path": "backend/app/controllers/spree/admin/payments_controller.rb", "relevance": "Main payment processing controller that calls @payment.process! and handles payment creation - likely where 502 errors are originating from"},
            {"path": "core/app/models/spree/payment_method.rb", "relevance": "Base payment method class with gateway delegation - webhook handling likely implemented in payment method subclasses (e.g., Spree::Gateway::Stripe)"},
            {"path": "core/app/models/spree/payment.rb", "relevance": "Core payment model with state machine - webhook confirmation likely updates payment state and would hang if webhook processing blocks"},
            {"path": "core/lib/spree/core/gateway_error.rb", "relevance": "Gateway error handling - would catch and handle webhook-related timeouts and exceptions"},
        ],
        "triage_duration_ms": 13172,
        "triage_tokens_in": 3842,
        "triage_tokens_out": 1456,
    },
    {
        "reporter_name": "James Park",
        "reporter_email": "james.park@example.com",
        "description": (
            "Product search returning zero results for all queries since the "
            "latest deploy at 09:15 UTC. The search index appears to be empty "
            "or disconnected. Customers cannot find any products. Verified on "
            "staging \u2014 works fine there."
        ),
        "severity": Severity.P1,
        "category": "storefront",
        "affected_component": "Product search index/query layer, likely Elasticsearch or similar search backend integration",
        "technical_summary": (
            "The incident reports that product search is returning zero results across "
            "all queries since a deploy at 09:15 UTC, with the search index appearing "
            "empty or disconnected. This is a critical customer-facing issue affecting "
            "core e-commerce functionality. The fact that staging works fine but production "
            "does not suggests either: (1) a deployment configuration difference between "
            "environments, (2) a search index rebuild that failed or wasn't triggered in "
            "production, (3) a connection string or credentials issue specific to the "
            "production search backend, or (4) a recent code change that broke the search "
            "query builder or index population logic.\n\n"
            "The provided source files show product search is accessed through multiple "
            "endpoints: `backend/app/controllers/spree/admin/search_controller.rb` for "
            "admin search and `api/app/controllers/spree/api/products_controller.rb` for "
            "API search. Both use `.ransack()` to build queries against the product scope. "
            "The ransack gem is a query builder that supports multiple backends. The empty "
            "index in production despite a working staging environment strongly indicates "
            "an infrastructure or deployment-time configuration issue rather than "
            "application code logic."
        ),
        "root_cause_hypothesis": (
            "The most likely causes are: (1) The search index (Elasticsearch, Solr, or "
            "similar) was not rebuilt or repopulated after the 09:15 UTC deploy, or the "
            "rebuild process failed silently; (2) A deployment configuration change altered "
            "the search backend connection parameters (host, port, credentials, index name) "
            "in production, causing queries to hit a wrong/empty index; (3) A recent code "
            "change modified how products are indexed or queries are constructed, breaking "
            "the search pipeline; or (4) The search backend service crashed or became "
            "unavailable in production during/after the deploy."
        ),
        "suggested_assignee": "platform-team",
        "confidence": 0.75,
        "recommended_actions": [
            "Immediately verify the search backend (Elasticsearch/Solr) is running and reachable in production: check service status, network connectivity, and logs",
            "Confirm the production search index exists and is not empty: query the backend directly (e.g., curl to Elasticsearch) to verify data",
            "Review the deployment logs from 09:15 UTC for any index rebuild, migration, or configuration change that occurred",
            "Compare production and staging search backend configuration (connection strings, index names, credentials) in environment variables and secrets",
            "Check the git diff from the latest deploy to identify any changes to: ransack configuration, product indexing logic, search controller code, or environment-specific search setup",
            "If index is empty or corrupted, trigger a full product index rebuild/reindex in production",
            "Monitor search query logs/metrics for error patterns that might indicate connection failures or query parsing issues",
            "Run a manual product search query against the backend to validate the fix and confirm zero-result issue is resolved",
        ],
        "related_files": [
            {"path": "api/app/controllers/spree/api/products_controller.rb", "relevance": "Contains the main product search endpoint using ransack; the index action is the primary customer-facing search"},
            {"path": "backend/app/controllers/spree/admin/search_controller.rb", "relevance": "Admin search endpoint; also uses ransack for product queries"},
            {"path": "core/lib", "relevance": "Likely contains search indexing configuration, ransack setup, and search backend integration"},
            {"path": ".github/workflows", "relevance": "Deployment workflow may include index rebuild steps; review for changes in the 09:15 UTC deploy"},
            {"path": "core/config", "relevance": "Search backend configuration and connection parameters likely stored here"},
        ],
        "triage_duration_ms": 12950,
        "triage_tokens_in": 3567,
        "triage_tokens_out": 1389,
    },
    {
        "reporter_name": "Sarah Kim",
        "reporter_email": "sarah.kim@example.com",
        "description": (
            "Admin panel showing 403 Forbidden for all non-super-admin users since "
            "the permission migration ran this morning. Store managers cannot access "
            "order management. Roughly 15 admin users affected."
        ),
        "severity": Severity.P2,
        "category": "admin",
        "affected_component": "Spree::PermissionSets, Admin authorization system",
        "technical_summary": (
            "Following this morning's permission migration, all non-super-admin users "
            "are receiving 403 Forbidden errors when accessing the admin panel. The issue "
            "affects ~15 store managers and admin users who previously had access to order "
            "management and other admin functions.\n\n"
            "The root cause appears to be a migration or code change in the permission "
            "system that altered how permissions are being granted to admin roles. Based "
            "on the codebase analysis, the permission system uses CanCan-style permission "
            "sets (UserManagement, UserDisplay, etc.) that are activated conditionally. "
            "The migration likely either: (1) changed the role-to-permission-set mapping, "
            "(2) failed to properly activate required permission sets for non-super-admin "
            "roles, or (3) introduced a bug in the permission inheritance or activation "
            "logic.\n\n"
            "Since non-super-admin users are affected but some access remains possible "
            "(suggesting the permission system itself isn't completely broken), the issue "
            "is likely scoped to specific permission sets not being activated for certain "
            "roles during the migration, or a conditional check that's now preventing "
            "activation for non-super-admin users."
        ),
        "root_cause_hypothesis": (
            "The permission migration this morning likely changed how roles are assigned "
            "permission sets, or introduced a conditional that prevents non-super-admin "
            "users from having required admin permission sets activated. Possible causes: "
            "(1) Permission set activation logic now incorrectly filters out non-super-admin "
            "users, (2) Migration failed to properly assign permission sets to existing "
            "roles during migration, (3) A conditional in the admin authorization check "
            "now requires super_admin role that didn't exist before."
        ),
        "suggested_assignee": "platform-team",
        "confidence": 0.85,
        "recommended_actions": [
            "Check git history for the permission migration that ran this morning - review all changes to permission set activation logic and role assignments",
            "Verify that non-super-admin roles still have required permission sets assigned in the database (check spree_role_permissions or equivalent join table)",
            "Review the admin authorization check (likely in admin/app/controllers or core/lib) to see if a super_admin-only condition was recently added",
            "Compare user roles before and after the migration - check if roles were dropped or permission sets deactivated",
            "Test permission activation manually: create a test user with store-manager role and verify UserManagement/UserDisplay permission sets activate correctly",
            "Check admin/app/controllers/spree/admin/base_controller.rb for authorization logic changes",
            "Review the migration file itself for any conditional logic that skips permission assignment for non-super-admin roles",
            "Consider rolling back the migration if no obvious fix is found, then re-run with verbose logging",
        ],
        "related_files": [
            {"path": "core/app/models/spree/permission_sets/user_management.rb", "relevance": "Defines permission set for user/admin management - critical for store manager access"},
            {"path": "core/app/models/spree/permission_sets/user_display.rb", "relevance": "Defines read-only user permissions - may be affected by migration"},
            {"path": "core/spec/models/spree/permission_sets/user_management_spec.rb", "relevance": "Tests show expected behavior - useful for validating fix"},
            {"path": "backend/spec/controllers/spree/admin/users_controller_spec.rb", "relevance": "Shows how authorization is tested in admin controllers - helps understand authorization flow"},
            {"path": "core/db/migrate/", "relevance": "Permission migration files from this morning - likely contains the breaking change"},
            {"path": "core/app/models/spree/ability.rb", "relevance": "Core authorization logic that loads and applies permission sets"},
            {"path": "core/app/models/spree/role.rb", "relevance": "Role model - check if permission_sets association or activation logic changed"},
            {"path": "admin/app/controllers/spree/admin/base_controller.rb", "relevance": "Admin base controller - likely has authorization checks that may have been modified"},
        ],
        "triage_duration_ms": 11614,
        "triage_tokens_in": 3215,
        "triage_tokens_out": 1278,
    },
    {
        "reporter_name": "Alex Rivera",
        "reporter_email": "ops@example.com",
        "description": (
            "Intermittent 504 Gateway Timeout on product detail pages during peak "
            "hours (12:00-14:00 UTC). Affects roughly 5% of requests. Response times "
            "spike from 200ms to 8s. Seems related to variant pricing calculations "
            "on products with 50+ variants."
        ),
        "severity": Severity.P2,
        "category": "storefront",
        "affected_component": "Product detail page variant pricing calculations, likely in Spree::Variant and Spree::Price models",
        "technical_summary": (
            "The incident manifests as intermittent 504 Gateway Timeouts affecting ~5% "
            "of requests to product detail pages during peak hours, with response times "
            "spiking from 200ms to 8s. The correlation with products having 50+ variants "
            "strongly suggests the root cause is inefficient variant pricing calculation "
            "logic. When a product has many variants, the product detail page likely "
            "iterates through all variants to calculate and display pricing information "
            "without proper query optimization. This causes N+1 query problems or expensive "
            "in-memory calculations that exceed request timeouts during peak load. The issue "
            "is intermittent because it only manifests when variant-heavy products are "
            "accessed concurrently, overwhelming the database or application thread pool.\n\n"
            "The most probable cause is missing database query optimization (eager loading) "
            "or unindexed lookups when fetching variant prices, combined with lack of "
            "caching for pricing calculations. Additionally, the pricing calculation logic "
            "in Spree::Variant or Spree::Price may perform sequential operations instead "
            "of batch operations, creating O(n) or worse complexity with respect to variant "
            "count.\n\n"
            "This affects the storefront product detail page rendering path and represents "
            "a major feature degradation (P2) as it completely blocks access to product "
            "pages during peak hours for a significant percentage of requests."
        ),
        "root_cause_hypothesis": (
            "Missing or inadequate eager loading of variant prices when rendering product "
            "detail pages, combined with inefficient pricing calculation logic that scales "
            "poorly with variant count. Likely N+1 queries when iterating through 50+ "
            "variants to calculate display prices, potentially within a serializer or view "
            "template. Secondary cause may be lack of Redis/memcache caching for variant "
            "pricing computations."
        ),
        "suggested_assignee": "platform-team",
        "confidence": 0.75,
        "recommended_actions": [
            "Check product detail page controller/serializer for variant loading logic - look for .includes(:prices) and similar eager loading calls",
            "Review Spree::Api::VariantSerializer and related product serializers for N+1 query patterns in pricing-related fields",
            "Add database query logging for product detail page requests with 50+ variants to confirm N+1 pattern",
            "Examine Spree::Variant#display_price and related pricing calculation methods for inefficient loops or repeated database calls",
            "Check if variant pricing serialization is cached - if not, implement caching layer (Redis) for price calculations",
            "Load test with a product containing 50+ variants to reproduce the issue in staging",
            "Review core/app/models/spree/variant.rb for pricing-related scopes and ensure they use batch queries",
            "Check if there are unindexed foreign key lookups on Spree::Price table (currency, country filters)",
            "Consider implementing variant pricing aggregation at database level rather than application level for products with many variants",
        ],
        "related_files": [
            {"path": "core/app/models/spree/variant.rb", "relevance": "Core variant model that likely contains pricing calculation methods and associations to Spree::Price"},
            {"path": "core/app/models/spree/price.rb", "relevance": "Price model that variant pricing queries depend on - check for eager loading associations"},
            {"path": "api/app/serializers/spree/api/variant_serializer.rb", "relevance": "API serializer for variants that likely calculates and returns pricing data - prime candidate for N+1 queries"},
            {"path": "api/app/serializers/spree/api/product_serializer.rb", "relevance": "Product serializer that may iterate through all variants to compute pricing information"},
            {"path": "api/app/controllers/spree/api/products_controller.rb", "relevance": "Product detail endpoint controller - check for query optimization in index/show actions"},
            {"path": "core/app/models/spree/product.rb", "relevance": "Product model - check variants association and related scopes for eager loading optimization"},
            {"path": "core/lib/spree/variant_selector.rb", "relevance": "If exists, likely contains variant filtering/pricing logic that may need optimization"},
        ],
        "triage_duration_ms": 13002,
        "triage_tokens_in": 3401,
        "triage_tokens_out": 1512,
    },
]


async def seed_database(db: AsyncSession) -> list[Incident]:
    """Populate the database with sample incidents if empty.

    All 4 incidents are seeded as DISPATCHED with real triage data, and the
    dispatch service generates tickets + notifications from the triage results.

    Returns the list of created incidents (for Langfuse trace seeding).
    """
    count_result = await db.execute(select(func.count(Incident.id)))
    existing = count_result.scalar_one()

    if existing > 0:
        logger.info("Database already has %d incidents — skipping seed", existing)
        return []

    logger.info("Seeding database with %d sample incidents...", len(SEED_INCIDENTS))

    created: list[Incident] = []
    for data in SEED_INCIDENTS:
        incident = Incident(
            reporter_name=data["reporter_name"],
            reporter_email=data["reporter_email"],
            description=data["description"],
            status=IncidentStatus.DISPATCHED,
            severity=data["severity"],
            category=data["category"],
            affected_component=data["affected_component"],
            technical_summary=data["technical_summary"],
            root_cause_hypothesis=data["root_cause_hypothesis"],
            suggested_assignee=data["suggested_assignee"],
            confidence=data["confidence"],
            recommended_actions=data["recommended_actions"],
            related_files=data["related_files"],
            validation_flags={"flags": [], "passed": True},
            injection_score=0.0,
        )
        db.add(incident)
        await db.flush()

        # Dispatch creates ticket + notifications from triage data
        await dispatch_incident(incident, db)
        created.append(incident)

    logger.info("Seed complete: %d incidents created with tickets + notifications", len(created))
    return created


def seed_langfuse_traces(incidents: list[Incident]) -> None:
    """Seed Langfuse with multi-span pipeline traces for each incident.

    Creates the same trace structure as the live triage pipeline:
    guardrail → context-retrieval → triage-generation → dispatch
    """
    from app.services.observability import trace_triage_pipeline

    model = "claude-haiku-4-5-20251001"
    triage_meta = {d["reporter_email"]: d for d in SEED_INCIDENTS}

    seeded = 0
    for incident in incidents:
        meta = triage_meta.get(incident.reporter_email)
        if not meta:
            continue

        severity = meta["severity"].value if meta["severity"] else "?"
        trace_triage_pipeline(
            str(incident.id),
            guardrail={
                "description": incident.description[:500],
                "passed": True,
                "injection_score": 0.0,
                "flags": [],
            },
            context_retrieval={
                "search_query": incident.description[:200],
                "total_indexed_files": 1247,
                "files_found": len(meta["related_files"]) if meta["related_files"] else 0,
                "files": [
                    {"path": f["path"], "extension": f["path"].rsplit(".", 1)[-1], "size_lines": 45}
                    for f in (meta["related_files"] or [])
                ],
            },
            generation={
                "model": model,
                "input": incident.description,
                "output": str({
                    "severity": severity,
                    "category": meta["category"],
                    "confidence": meta["confidence"],
                    "affected_component": meta["affected_component"],
                    "technical_summary": (meta["technical_summary"] or "")[:300],
                    "root_cause_hypothesis": (meta["root_cause_hypothesis"] or "")[:200],
                    "recommended_actions_count": len(meta["recommended_actions"] or []),
                    "related_files_count": len(meta["related_files"] or []),
                }),
                "tokens_in": meta["triage_tokens_in"],
                "tokens_out": meta["triage_tokens_out"],
                "duration_ms": meta["triage_duration_ms"],
                "severity": severity,
                "category": meta["category"],
                "confidence": meta["confidence"],
                "affected_component": meta["affected_component"],
                "suggested_assignee": meta["suggested_assignee"],
            },
            dispatch={
                "ticket_id": str(incident.id)[:8] + "-ticket",
                "email_sent": True,
                "email_recipient": f"{meta['suggested_assignee'].replace('-team', '')}-oncall@example.com",
                "chat_sent": True,
                "chat_channel": "#incidents",
            },
        )
        seeded += 1

    logger.info("Langfuse pipeline traces seeded: %d incidents", seeded)
