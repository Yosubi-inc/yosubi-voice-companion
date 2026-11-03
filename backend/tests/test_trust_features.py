from test_safety import client


def setup_circle(api):
    api.put('/profiles/p/consent', json={'granted': True})
    base = '/safety/profiles/p'
    contact = api.post(base + '/contacts', json={'name': 'Ana', 'role': 'family', 'consent': True}).json()['id']
    other = api.post(base + '/contacts', json={'name': 'Luis', 'consent': True}).json()['id']
    grant = api.post(base + f'/contacts/{contact}/grants', json={'permission': 'receive_escalation', 'consent': True}).json()['id']
    return base, contact, other, grant


def test_escalation_decisions_and_revocation(client):
    api, _ = client
    base, contact, other, grant = setup_circle(api)
    request = {'contact_id': contact, 'permission': 'receive_escalation', 'consent': True}
    assert api.post(base + '/escalations', json={**request, 'permission': 'save_incident'}).status_code == 403
    for decision in ('approved', 'denied'):
        response = api.post(base + '/escalations', json=request)
        assert response.status_code == 200
        request_id = response.json()['id']
        path = base + f'/escalations/{request_id}/decision'
        assert api.post(path, json={'contact_id': other, 'decision': decision, 'consent': True}).status_code == 403
        assert api.post(path, json={'contact_id': contact, 'decision': decision, 'consent': True}).json()['status'] == decision
        assert api.post(path, json={'contact_id': contact, 'decision': decision, 'consent': True}).status_code == 409
    pending = api.post(base + '/escalations', json=request).json()['id']
    api.post(base + f'/grants/{grant}/revoke', json={'consent': True})
    assert api.post(base + f'/escalations/{pending}/decision', json={'contact_id': contact, 'decision': 'approved', 'consent': True}).status_code == 403
    assert api.post(base + '/escalations', json=request).status_code == 403
    assert [item['event'] for item in api.get(base + '/activity').json()] == ['requested', 'approved', 'requested', 'denied', 'requested']


def test_incidents_filter_and_consent(client):
    api, _ = client
    base, contact, _, _ = setup_circle(api)
    incident = api.post(base + '/incidents', json={'summary': 'Suspicious call', 'consent': True}).json()['id']
    path = base + f'/incidents/{incident}'
    assert api.patch(path, json={'status': 'resolved', 'consent': False}).status_code == 403
    assert api.patch(path, json={'status': 'resolved', 'consent': True, 'contact_id': contact}).status_code == 403
    assert api.patch(path, json={'status': 'resolved', 'consent': True}).json()['status'] == 'resolved'
    assert len(api.get(base + '/incidents', params={'status': 'resolved'}).json()) == 1
    assert api.get(base + '/incidents', params={'status': 'open'}).json() == []
    assert api.get('/safety/profiles/other/incidents').json() == []
    api.put('/profiles/p/consent', json={'granted': False})
    assert api.patch(path, json={'status': 'open', 'consent': True}).status_code == 403


def test_decision_requires_each_live_grant(client):
    api, _ = client
    base, contact, _, _ = setup_circle(api)
    grant = api.post(base + f'/contacts/{contact}/grants', json={'permission': 'save_incident', 'consent': True}).json()['id']
    request = api.post(base + '/escalations', json={'contact_id': contact, 'permission': 'save_incident', 'consent': True}).json()['id']
    api.post(base + f'/grants/{grant}/revoke', json={'consent': True})
    assert api.post(base + f'/escalations/{request}/decision', json={'contact_id': contact, 'decision': 'approved', 'consent': True}).status_code == 403


def test_lessons_in_both_languages(client):
    api, _ = client
    en = api.get('/safety/lessons', params={'language': 'en'}).json()
    es = api.get('/safety/lessons', params={'language': 'es'}).json()
    assert len(en) >= 2 and [x['id'] for x in en] == [x['id'] for x in es]
    assert all(x['title'] and x['text'] and x['language'] == 'en' for x in en)
    assert all(x['title'] and x['text'] and x['language'] == 'es' for x in es)
    assert en[0]['text'] != es[0]['text']
