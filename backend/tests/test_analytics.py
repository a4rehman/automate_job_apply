import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analytics_endpoints(client: AsyncClient, auth_headers):
    # Test KPI metrics
    res_kpis = await client.get("/api/v1/analytics/kpis", headers=auth_headers)
    assert res_kpis.status_code == 200
    kpis = res_kpis.json()
    assert "total_jobs_tracked" in kpis
    assert "high_matches_count" in kpis
    assert "applications_submitted" in kpis

    # Test Funnel stats
    res_funnel = await client.get("/api/v1/analytics/funnel", headers=auth_headers)
    assert res_funnel.status_code == 200
    funnel = res_funnel.json()
    assert "discovered" in funnel
    assert "approved" in funnel
    assert "submitted" in funnel
