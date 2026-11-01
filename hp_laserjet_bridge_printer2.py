import json
from urllib import request as urlrequest

import hp_laserjet_promotion_bridge as bridge


def api_json(method, url, key, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=data, method=method)
    req.add_header("X-Print-Bridge-Key", key)
    req.add_header("X-Print-Bridge-Id", "printer2")
    req.add_header("Content-Type", "application/json")
    with urlrequest.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


bridge.api_json = api_json
bridge.main()
