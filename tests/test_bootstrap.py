from app import create_app

def _init_db(app):
    from app.main_startup import initialize_database
    with app.app_context():
        initialize_database(app)


def test_bootstrap_endpoint_returns_expected_fields():
    app = create_app('testing')
    _init_db(app)
    client = app.test_client()
    resp = client.get('/api/v1/system/bootstrap')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    for key in ['has_active_user', 'first_sync_completed', 'sync_in_progress', 'total_cves', 'next_refresh_seconds']:
        assert key in data


def test_sync_progress_endpoint_accessible_in_initial_state():
    app = create_app('testing')
    _init_db(app)
    client = app.test_client()
    resp = client.get('/api/v1/sync/progress')
    assert resp.status_code in (200, 401, 403)
    if resp.status_code == 200:
        data = resp.get_json()
        assert 'status' in data
